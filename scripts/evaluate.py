#!/usr/bin/env python
"""ROBIN-FPGA evaluation entry point with calibrated conformal sign-off.

Usage
-----
    python scripts/evaluate.py --checkpoint runs/best.pt \
                               --design data/benchmarks/gemm_systolic/ \
                               --seeds 10 \
                               --alpha 0.05 \
                               --output eval/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from robin_fpga.agent import Agent
from robin_fpga.environment import Environment, PVTCorner
from robin_fpga.evaluator import Evaluator
from robin_fpga.utils import ensure_dir, seed_everything, setup_logging

log = logging.getLogger("robin_fpga.evaluate")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ROBIN-FPGA evaluation")
    p.add_argument("--checkpoint", required=True, type=Path)
    p.add_argument("--design", required=True, type=Path)
    p.add_argument("--seeds", type=int, default=10, help="number of held-out P&R seeds")
    p.add_argument("--alpha", type=float, default=0.05, help="conformal miscoverage target")
    p.add_argument("--beta", type=float, default=0.20, help="CVaR tail mass")
    p.add_argument("--tool", choices=["vivado", "quartus"], default="vivado")
    p.add_argument("--device", default="xcve2302-sfva784-2MP-e-S")
    p.add_argument("--tool-version", default="2024.2")
    p.add_argument("--output", type=Path, default=Path("./eval"))
    p.add_argument("--log-level", default="INFO")
    return p


def main() -> int:
    args = build_argparser().parse_args()
    ensure_dir(args.output)
    setup_logging(level=args.log_level, log_file=args.output / "eval.log")
    seed_everything(42)

    log.info(f"Loading checkpoint: {args.checkpoint}")
    agent = Agent.from_checkpoint(args.checkpoint)
    agent.conformal.alpha = args.alpha

    rtl_path = args.design / "design.v"
    xdc_path = args.design / ("constraints.xdc" if args.tool == "vivado" else "constraints.sdc")

    env = Environment(
        rtl_path=rtl_path,
        device=args.device,
        constraints=xdc_path,
        tool=args.tool,
        tool_version=args.tool_version,
        seeds=list(range(101, 101 + args.seeds)),  # disjoint from training seeds
        corners=None,
        workdir=ensure_dir(args.output / "tool_runs"),
        parallel=8,
    )

    evaluator = Evaluator(agent, env)
    report = evaluator.evaluate(
        num_seeds=args.seeds,
        beta=args.beta,
        save_path=args.output / "report.json",
    )

    log.info("=" * 70)
    log.info(f"Design:           {report.design}")
    log.info(f"Device:           {report.device}")
    log.info(f"Closure rate:     {report.closure_rate:.1%} ({args.seeds} seeds)")
    log.info(f"sigma(WNS):       {report.sigma_wns:.3f} ns")
    log.info(f"Mean WNS:         {report.mean_wns:+.3f} ns")
    log.info(f"CVaR_{args.beta} WNS:    {report.cvar_wns:+.3f} ns")
    log.info(f"Empirical coverage @ 1-alpha={1-args.alpha:.2f}: {report.empirical_coverage:.3f}")
    log.info(f"Accepted:         {report.accepted}")
    log.info(f"Audit hash:       {report.audit_hash[:16]}...")
    log.info("=" * 70)

    return 0 if report.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
