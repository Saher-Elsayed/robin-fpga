"""FPGA toolchain environment wrapper.

Wraps AMD Vivado and Intel Quartus Prime Pro into a Gym-style environment that
the agent can drive. Each `step(action)` invokes the toolchain across K seeds and
|Theta| corners, parses the vendor reports through a device-agnostic normalizer
(Figure 5 of the paper), and returns the reward distribution.

The Tcl scripts that perform the actual flow are in flows/{vivado,quartus}/.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class PVTCorner:
    """A single PVT corner specification."""
    process: str           # "SS", "TT", "FF", "SF", "FS"
    voltage: str           # "nominal", "high", "low"
    temperature: float     # degrees Celsius

    def slug(self) -> str:
        t = f"{int(self.temperature)}" if self.temperature >= 0 else f"m{abs(int(self.temperature))}"
        return f"{self.process}_{self.voltage}_{t}"


@dataclass
class ToolReport:
    """Parsed report from a single P&R run."""
    wns: float                    # Worst Negative Slack (ns)
    tns: float                    # Total Negative Slack (ns)
    utilization: dict[str, float] # per-resource utilization percentages
    congestion_pct: list[float]   # routing-congestion histogram percentiles
    power_dynamic: float          # dynamic power (W)
    power_static: float           # static power (W)
    latency_ns: float             # critical-path latency (ns)
    route_failed: bool = False    # whether route_design failed outright
    seed: int = 0
    corner: Optional[PVTCorner] = None
    raw_log_path: Optional[Path] = None


class Environment:
    """FPGA toolchain environment with parallel seed/corner fan-out.

    Parameters
    ----------
    rtl_path : str | Path
        Path to RTL or HLS source.
    device : str
        Target device part number, e.g. "xcve2302-sfva784-2MP-e-S" (Versal) or
        "AGIB027R29A1E2VR0" (Agilex).
    constraints : str | Path
        Path to vendor constraint file (.xdc for Vivado, .sdc for Quartus).
    tool : {"vivado", "quartus"}
        Which toolchain to drive.
    tool_version : str
        Tool version string (e.g. "2024.2"), recorded in audit trail.
    seeds : iterable of int
        P&R seeds to fan out over per step.
    corners : iterable of PVTCorner
        PVT corners to evaluate per step.
    workdir : str | Path
        Working directory for tool runs (one subfolder per step).
    parallel : int
        Maximum number of parallel tool processes.
    """

    def __init__(
        self,
        rtl_path: str | Path,
        device: str,
        constraints: str | Path,
        tool: str = "vivado",
        tool_version: str = "2024.2",
        seeds: Optional[list[int]] = None,
        corners: Optional[list[PVTCorner]] = None,
        workdir: str | Path = "./runs",
        parallel: int = 8,
    ) -> None:
        if tool not in {"vivado", "quartus"}:
            raise ValueError(f"unsupported tool: {tool}")
        self.rtl_path = Path(rtl_path).resolve()
        self.device = device
        self.constraints = Path(constraints).resolve()
        self.tool = tool
        self.tool_version = tool_version
        self.seeds = list(seeds or [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.corners = list(corners or _default_corners())
        self.workdir = Path(workdir).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.parallel = parallel
        self._step_index = 0

    # ----- step / reset -------------------------------------------------------

    def reset(self) -> dict:
        """Initial synthesis pass — returns the post-synthesis observation."""
        log.info(f"Reset environment for {self.rtl_path.name} on {self.device}")
        self._step_index = 0
        return self._observe_post_synth()

    def step(self, action: dict) -> tuple[list[ToolReport], dict]:
        """Run one P&R step across all (seed, corner) combinations.

        Parameters
        ----------
        action : dict
            Directive bundle from the policy; see flows/<tool>/README.md for keys.

        Returns
        -------
        reports : list[ToolReport]
            One report per (seed, corner) combination.
        info : dict
            Diagnostics (wall-clock, return distribution, etc.).
        """
        self._step_index += 1
        step_dir = self.workdir / f"step_{self._step_index:04d}"
        step_dir.mkdir(parents=True, exist_ok=True)

        # Write action as Tcl deltas
        action_tcl = self._write_action_tcl(action, step_dir)

        # Fan out across (seed, corner) combinations
        tasks = [(s, c) for s in self.seeds for c in self.corners]
        reports: list[ToolReport] = []
        start = time.time()
        with ThreadPoolExecutor(max_workers=self.parallel) as ex:
            futures = {
                ex.submit(self._run_single, action_tcl, seed, corner, step_dir): (seed, corner)
                for seed, corner in tasks
            }
            for fut in as_completed(futures):
                seed, corner = futures[fut]
                try:
                    report = fut.result()
                    reports.append(report)
                except Exception as exc:
                    log.error(f"P&R failed for seed={seed} corner={corner.slug()}: {exc}")
                    reports.append(self._failed_report(seed, corner))
        info = {
            "wall_clock_sec": time.time() - start,
            "num_runs": len(reports),
            "step": self._step_index,
        }
        return reports, info

    # ----- private helpers ----------------------------------------------------

    def _observe_post_synth(self) -> dict:
        """Run initial synthesis to extract the timing graph and tab features."""
        log.info("Running initial synthesis (this can take minutes)")
        # Implementation: invoke flows/<tool>/synth.tcl, parse outputs.
        # Returns a dict with keys: graph (node_feats, adj), tab_feats.
        return {"node_feats": None, "adj": None, "tab_feats": None}

    def _write_action_tcl(self, action: dict, step_dir: Path) -> Path:
        """Serialize the action dict to a vendor Tcl delta file."""
        path = step_dir / f"action.{'xdc' if self.tool == 'vivado' else 'qsf'}"
        with open(path, "w") as f:
            for k, v in action.items():
                if self.tool == "vivado":
                    f.write(f"set_property {k} {v} [current_design]\n")
                else:
                    f.write(f"set_global_assignment -name {k} {v}\n")
        return path

    def _run_single(
        self,
        action_tcl: Path,
        seed: int,
        corner: PVTCorner,
        step_dir: Path,
    ) -> ToolReport:
        """Run a single (seed, corner) P&R and parse the report."""
        run_dir = step_dir / f"seed_{seed}_corner_{corner.slug()}"
        run_dir.mkdir(parents=True, exist_ok=True)

        cmd = self._build_command(action_tcl, seed, corner, run_dir)
        log.debug(f"Running: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, cwd=run_dir, check=True, capture_output=True, timeout=7200)
        except subprocess.TimeoutExpired:
            log.warning(f"Run timeout for seed={seed} corner={corner.slug()}")
            return self._failed_report(seed, corner)
        return self._parse_report(run_dir, seed, corner)

    def _build_command(
        self,
        action_tcl: Path,
        seed: int,
        corner: PVTCorner,
        run_dir: Path,
    ) -> list[str]:
        """Construct the tool invocation command."""
        if self.tool == "vivado":
            return [
                "vivado", "-mode", "batch",
                "-source", "flows/vivado/place_route.tcl",
                "-tclargs",
                "--rtl", str(self.rtl_path),
                "--part", self.device,
                "--xdc", str(self.constraints),
                "--action", str(action_tcl),
                "--seed", str(seed),
                "--corner", corner.slug(),
                "--out", str(run_dir),
            ]
        else:
            return [
                "quartus_sh", "-t", "flows/quartus/fit.tcl",
                "--rtl", str(self.rtl_path),
                "--part", self.device,
                "--sdc", str(self.constraints),
                "--action", str(action_tcl),
                "--seed", str(seed),
                "--corner", corner.slug(),
                "--out", str(run_dir),
            ]

    def _parse_report(
        self, run_dir: Path, seed: int, corner: PVTCorner
    ) -> ToolReport:
        """Parse the vendor report into the canonical schema."""
        report_path = run_dir / "report.json"
        if not report_path.exists():
            return self._failed_report(seed, corner)
        with open(report_path) as f:
            data = json.load(f)
        return ToolReport(
            wns=float(data["wns"]),
            tns=float(data["tns"]),
            utilization=dict(data["utilization"]),
            congestion_pct=list(data["congestion_pct"]),
            power_dynamic=float(data["power_dynamic"]),
            power_static=float(data["power_static"]),
            latency_ns=float(data["latency_ns"]),
            route_failed=bool(data.get("route_failed", False)),
            seed=seed,
            corner=corner,
            raw_log_path=run_dir / "tool.log",
        )

    def _failed_report(self, seed: int, corner: PVTCorner) -> ToolReport:
        """Sentinel report for a failed run."""
        return ToolReport(
            wns=-10.0, tns=-100.0, utilization={}, congestion_pct=[100.0],
            power_dynamic=0.0, power_static=0.0, latency_ns=999.0,
            route_failed=True, seed=seed, corner=corner,
        )


# ----- module-level helpers --------------------------------------------------

def _default_corners() -> list[PVTCorner]:
    """A balanced 3-corner set: slow-slow, typical-typical, fast-fast."""
    return [
        PVTCorner("SS", "nominal", 125),
        PVTCorner("TT", "nominal", 25),
        PVTCorner("FF", "nominal", -40),
    ]


def returns_from_reports(
    reports: list[ToolReport],
    clip_wns: float = 1.0,
    w_wns: float = 1.0,
    w_tns: float = 0.3,
    kappa_util: float = 5.0,
    kappa_fail: float = 10.0,
    util_budgets: Optional[dict[str, float]] = None,
    clk_period_ns: float = 5.0,
) -> np.ndarray:
    """Compute the reward distribution {R_{k,θ}} from a batch of reports.

    Implements Equation (3) of the paper:
        r = w_WNS * clip(WNS/T_clk, -1, 1)
          + w_TNS * (-sat(|TNS|/T_clk))
          - kappa * sum_i (U_i - U_max^i)^+
          - 1[route_fail] * kappa_fail
    """
    util_budgets = util_budgets or {"LUT": 70.0, "FF": 70.0, "BRAM": 80.0, "DSP": 80.0, "URAM": 80.0}
    returns = []
    for r in reports:
        if r.route_failed:
            returns.append(-kappa_fail)
            continue
        # WNS reward (clipped, normalized)
        wns_n = r.wns / clk_period_ns
        wns_term = w_wns * max(-clip_wns, min(clip_wns, wns_n))
        # TNS penalty (saturating)
        tns_n = abs(r.tns) / clk_period_ns
        tns_term = -w_tns * (tns_n / (1.0 + tns_n))
        # Utilization Lagrangian penalty
        util_pen = 0.0
        for k, budget in util_budgets.items():
            actual = r.utilization.get(k, 0.0)
            util_pen += max(0.0, actual - budget)
        util_term = -kappa_util * util_pen / 100.0  # normalize pp -> [0,1]
        returns.append(wns_term + tns_term + util_term)
    return np.asarray(returns, dtype=np.float64)
