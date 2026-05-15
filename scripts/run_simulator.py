#!/usr/bin/env python
"""Run the calibrated simulator to regenerate every paper figure's CSV.

Usage
-----
    python scripts/run_simulator.py --output data/results/ --seed 42
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from robin_fpga.simulator import Simulator, SimulatorConfig
from robin_fpga.utils import seed_everything, setup_logging

log = logging.getLogger("robin_fpga.simulator")


def main() -> int:
    p = argparse.ArgumentParser(description="ROBIN-FPGA simulator data generator")
    p.add_argument("--output", type=Path, default=Path("data/results"))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args()

    setup_logging(level=args.log_level)
    seed_everything(args.seed)

    sim = Simulator(SimulatorConfig(seed=args.seed, output_dir=str(args.output)))
    paths = sim.generate_all()

    log.info("=" * 60)
    log.info(f"Generated {len(paths)} simulator output files:")
    for name, path in paths.items():
        size_kb = path.stat().st_size / 1024.0
        log.info(f"  {name:20s} -> {path} ({size_kb:.1f} KB)")
    log.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
