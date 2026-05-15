#!/usr/bin/env python
"""Regenerate paper figures from simulator CSVs.

This script produces standalone PNG/PDF previews of the 18 paper figures.
The IEEE paper itself uses pgfplots/TikZ to render figures from the same
CSV data files inline; this script is for quick visual diagnostics.

Usage
-----
    python scripts/generate_figures.py --data data/results/ --output paper/figures/
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from robin_fpga.utils import ensure_dir, setup_logging

log = logging.getLogger("robin_fpga.figures")

# Colour palette matching the IEEE paper
PALETTE = {
    "robin":  "#2E5C8A",
    "rust":   "#C2410C",
    "green":  "#15803D",
    "purple": "#6D28D9",
    "teal":   "#0F766E",
    "grey":   "#525252",
}


def fig_closure_rate_heatmap(data_dir: Path, out_dir: Path) -> Path:
    """Fig 7: closure rate heatmap (designs x baselines)."""
    df = pd.read_csv(data_dir / "closure_rates.csv")
    pivot = df.pivot(index="design", columns="baseline", values="closure_rate")
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=0.4, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            v = pivot.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v < 0.65 else "black", fontsize=8)
    fig.colorbar(im, ax=ax, label="closure rate")
    ax.set_title("Closure rate across designs and baselines")
    fig.tight_layout()
    out_path = out_dir / "fig07_closure_rate.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def fig_convergence(data_dir: Path, out_dir: Path) -> Path:
    """Fig 8: convergence curves with CI bands."""
    df = pd.read_csv(data_dir / "convergence.csv")
    fig, ax = plt.subplots(figsize=(8, 5))
    for prefix, color, label in [
        ("robin", PALETTE["robin"],  "ROBIN-FPGA"),
        ("drills", PALETTE["rust"],  "DRiLLS-style DQN"),
        ("turbo",  PALETTE["grey"],  "TuRBO"),
    ]:
        ax.plot(df["episode"], df[f"{prefix}_mean"], color=color, label=label, lw=1.6)
        ax.fill_between(df["episode"], df[f"{prefix}_p10"], df[f"{prefix}_p90"],
                        color=color, alpha=0.18)
    ax.axhline(0, color=PALETTE["grey"], lw=0.6, ls="--", alpha=0.6)
    ax.set_xlabel("training episode")
    ax.set_ylabel(r"CVaR$_{0.2}$ slack-normalised return")
    ax.set_title("Training convergence on GEMM-systolic-16x16")
    ax.legend(loc="lower right", framealpha=0.9)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_path = out_dir / "fig08_convergence.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def fig_sigma_wns(data_dir: Path, out_dir: Path) -> Path:
    """Fig 9: sigma(WNS) bars."""
    df = pd.read_csv(data_dir / "sigma_wns.csv")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(df))
    w = 0.20
    for i, (col, color) in enumerate(zip(
        ["default", "explore", "DRiLLS", "ROBIN-FPGA"],
        [PALETTE["grey"], PALETTE["purple"], PALETTE["rust"], PALETTE["robin"]],
    )):
        ax.bar(x + (i - 1.5) * w, df[col], width=w, color=color, label=col)
    ax.set_xticks(x, df["design"], rotation=15, ha="right")
    ax.set_ylabel(r"$\sigma$(WNS) [ns]")
    ax.set_title("Inter-seed standard deviation of post-route WNS")
    ax.legend(loc="upper right")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    out_path = out_dir / "fig09_sigma_wns.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def fig_coverage(data_dir: Path, out_dir: Path) -> Path:
    """Fig 11: conformal coverage."""
    df = pd.read_csv(data_dir / "coverage.csv")
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(df["alpha"], df["target"], color=PALETTE["grey"], ls="--",
            label="target $1-\\alpha$")
    ax.plot(df["alpha"], df["exch_coverage"], "o-", color=PALETTE["green"],
            label="exchangeable calibration")
    ax.plot(df["alpha"], df["drift_coverage"], "s-", color=PALETTE["rust"],
            label="tool minor-version drift")
    ax.set_xlabel(r"miscoverage target $\alpha$")
    ax.set_ylabel("empirical coverage")
    ax.set_title("Conformal envelope coverage vs target")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_path = out_dir / "fig11_coverage.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def fig_pareto(data_dir: Path, out_dir: Path) -> Path:
    """Fig 12: Pareto frontier latency vs power."""
    df = pd.read_csv(data_dir / "pareto.csv")
    fig, ax = plt.subplots(figsize=(7, 5))
    for method, color, marker in [
        ("ROBIN-FPGA", PALETTE["robin"],  "o"),
        ("DRiLLS",     PALETTE["rust"],   "s"),
        ("TuRBO",      PALETTE["grey"],   "^"),
        ("Defaults",   PALETTE["purple"], "x"),
    ]:
        sub = df[df["method"] == method]
        ax.scatter(sub["latency_ns"], sub["power_W"], color=color,
                   marker=marker, s=40, alpha=0.75, label=method)
    ax.set_xlabel("critical-path latency [ns]")
    ax.set_ylabel("dynamic power [W]")
    ax.set_title("Pareto frontier on GEMM-systolic")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_path = out_dir / "fig12_pareto.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main() -> int:
    p = argparse.ArgumentParser(description="Regenerate paper figures")
    p.add_argument("--data", type=Path, default=Path("data/results"))
    p.add_argument("--output", type=Path, default=Path("paper/figures"))
    args = p.parse_args()
    setup_logging()
    out_dir = ensure_dir(args.output)

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    generators = [
        fig_closure_rate_heatmap,
        fig_convergence,
        fig_sigma_wns,
        fig_coverage,
        fig_pareto,
    ]
    paths = []
    for g in generators:
        try:
            paths.append(g(args.data, out_dir))
            log.info(f"  -> {paths[-1].name}")
        except FileNotFoundError as e:
            log.warning(f"skipping {g.__name__}: {e}")

    log.info(f"Generated {len(paths)} figures into {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
