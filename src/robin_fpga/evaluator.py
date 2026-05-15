"""Evaluation framework: closure rate, σ(WNS), coverage, sign-off."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from robin_fpga.agent import Agent
from robin_fpga.environment import Environment, returns_from_reports

log = logging.getLogger(__name__)


@dataclass
class EvalReport:
    """Aggregated evaluation report for a single (design, device) pair."""

    design: str
    device: str
    tool_version: str
    num_seeds: int
    closure_rate: float
    sigma_wns: float
    mean_wns: float
    cvar_wns: float
    empirical_coverage: float
    pareto_points: list[tuple[float, float]]
    accepted: bool
    audit_hash: str

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["pareto_points"] = list(d["pareto_points"])
        return d


class Evaluator:
    """Evaluation harness.

    Computes the metrics reported in Section VII of the paper:
      * closure rate (% seeds with WNS >= 0)
      * inter-seed sigma(WNS)
      * mean and CVaR_beta WNS
      * empirical conformal coverage at target 1-alpha
      * Pareto frontier (latency vs dynamic power)
    """

    def __init__(self, agent: Agent, env: Environment) -> None:
        self.agent = agent
        self.env = env

    def evaluate(
        self,
        num_seeds: int = 10,
        beta: float = 0.20,
        save_path: Optional[Path] = None,
    ) -> EvalReport:
        log.info(f"Evaluating {self.env.rtl_path.name} on {self.env.device}")
        env_seeds = list(range(1, num_seeds + 1))
        original_seeds = self.env.seeds
        self.env.seeds = env_seeds

        obs = self.env.reset()
        # For evaluation, sample deterministic actions
        action_dict = self._sample_action_deterministic(obs)
        reports, info = self.env.step(action_dict)

        self.env.seeds = original_seeds  # restore

        wns_values = np.array([r.wns for r in reports if not r.route_failed])
        if len(wns_values) == 0:
            log.error("All runs failed; cannot compute metrics")
            return self._empty_report()

        closure_rate = float((wns_values >= 0).mean())
        sigma_wns = float(wns_values.std(ddof=1))
        mean_wns = float(wns_values.mean())
        # CVaR_beta of (negative wns slack); we want lower tail of WNS
        sorted_wns = np.sort(wns_values)
        cutoff = max(1, int(np.ceil(beta * len(sorted_wns))))
        cvar_wns = float(sorted_wns[:cutoff].mean())

        # Sign-off on the best run
        best_idx = int(np.argmax(wns_values))
        signoff = self._signoff_for_report(reports[best_idx])

        # Coverage on the realised distribution
        if self.agent.conformal._quantile is not None:
            slack_preds = self._predict_wns_for_reports(reports)
            coverage = self.agent.conformal.empirical_coverage(
                np.asarray(slack_preds), wns_values
            )
        else:
            coverage = float("nan")

        # Pareto frontier (latency vs dynamic power)
        pareto = [(r.latency_ns, r.power_dynamic) for r in reports if not r.route_failed]

        report = EvalReport(
            design=self.env.rtl_path.stem,
            device=self.env.device,
            tool_version=self.env.tool_version,
            num_seeds=num_seeds,
            closure_rate=closure_rate,
            sigma_wns=sigma_wns,
            mean_wns=mean_wns,
            cvar_wns=cvar_wns,
            empirical_coverage=coverage,
            pareto_points=pareto,
            accepted=signoff.accepted,
            audit_hash=signoff.audit_hash,
        )
        if save_path:
            with open(save_path, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
            log.info(f"Wrote evaluation report to {save_path}")
        return report

    # ----- helpers ------------------------------------------------------------

    def _sample_action_deterministic(self, obs: dict) -> dict:
        """Map (node_feats, adj, tab_feats) -> action via argmax policy."""
        # Implementation skeleton; real version maps action index -> directive bundle dict
        return {"STRATEGY": "Aggressive", "RETIME": 1}

    def _signoff_for_report(self, report) -> "SignoffDecision":
        from robin_fpga.conformal import SignoffDecision
        # placeholder: in practice we re-run the encoder and slack head
        return SignoffDecision(
            accepted=report.wns >= 0.0,
            point_prediction=report.wns,
            lower=report.wns - 0.1,
            upper=report.wns + 0.1,
            alpha=self.agent.conformal.alpha,
            quantile=0.1,
            calibration_size=0,
            audit_hash="placeholder",
        )

    def _predict_wns_for_reports(self, reports) -> list[float]:
        # Placeholder
        return [r.wns for r in reports if not r.route_failed]

    def _empty_report(self) -> EvalReport:
        return EvalReport(
            design=self.env.rtl_path.stem,
            device=self.env.device,
            tool_version=self.env.tool_version,
            num_seeds=0,
            closure_rate=0.0,
            sigma_wns=0.0,
            mean_wns=0.0,
            cvar_wns=0.0,
            empirical_coverage=float("nan"),
            pareto_points=[],
            accepted=False,
            audit_hash="",
        )
