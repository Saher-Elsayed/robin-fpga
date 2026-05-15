#!/usr/bin/env python
"""ROBIN-FPGA training entry point.

Usage
-----
    python scripts/train.py --config configs/versal.yaml \
                            --design data/benchmarks/gemm_systolic/ \
                            --episodes 1200 \
                            --output runs/gemm_versal/

Or via the installed entry point:
    robin-fpga train --config configs/versal.yaml ...
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure src/ is importable when running from a checkout
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from robin_fpga.agent import Agent, AgentConfig
from robin_fpga.encoder import EncoderConfig
from robin_fpga.environment import Environment, PVTCorner
from robin_fpga.trainer import Trainer, TrainerConfig
from robin_fpga.utils import (
    ensure_dir,
    get_device,
    load_yaml,
    seed_everything,
    setup_logging,
)

log = logging.getLogger("robin_fpga.train")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ROBIN-FPGA training")
    p.add_argument("--config", required=True, type=Path, help="YAML config file")
    p.add_argument("--design", required=True, type=Path, help="benchmark design directory")
    p.add_argument("--episodes", type=int, default=None, help="override episode count")
    p.add_argument("--output", type=Path, default=Path("./runs"), help="output directory")
    p.add_argument("--device", choices=["cpu", "cuda"], default=None)
    p.add_argument("--log-level", default="INFO")
    p.add_argument(
        "--override",
        action="append",
        default=[],
        help="key.path=value config overrides (repeatable)",
    )
    return p


def apply_overrides(cfg: dict, overrides: list[str]) -> dict:
    """Apply --override foo.bar=42 style overrides to a config dict."""
    for ov in overrides:
        if "=" not in ov:
            log.warning(f"ignoring invalid override: {ov}")
            continue
        key, value = ov.split("=", 1)
        # parse value heuristically
        try:
            value = float(value) if "." in value else int(value)
        except ValueError:
            if value.lower() in {"true", "false"}:
                value = value.lower() == "true"
        cursor = cfg
        keys = key.split(".")
        for k in keys[:-1]:
            cursor = cursor.setdefault(k, {})
        cursor[keys[-1]] = value
    return cfg


def main() -> int:
    args = build_argparser().parse_args()
    setup_logging(level=args.log_level, log_file=args.output / "train.log")
    log.info(f"Loading config: {args.config}")

    cfg = load_yaml(args.config)
    if cfg.get("extends"):
        # very small "extends" implementation
        base = load_yaml(args.config.parent / cfg["extends"])
        base.update(cfg)
        cfg = base
        cfg.pop("extends", None)

    cfg = apply_overrides(cfg, args.override)

    seed = int(cfg.get("experiment", {}).get("seed", 42))
    seed_everything(seed)
    log.info(f"Seed set to {seed}; device = {args.device or get_device()}")

    # Build agent
    agent_cfg = AgentConfig(
        encoder=EncoderConfig(
            node_feat_dim=cfg["agent"]["encoder"].get("node_feat_dim", 16),
            edge_feat_dim=cfg["agent"]["encoder"].get("edge_feat_dim", 4),
            tab_feat_dim=cfg["agent"]["encoder"].get("tab_feat_dim", 32),
            gat_heads=cfg["agent"]["encoder"].get("gat_heads", 4),
            gat_hidden_1=cfg["agent"]["encoder"].get("gat_hidden_1", 32),
            gat_hidden_2=cfg["agent"]["encoder"].get("gat_hidden_2", 64),
            mlp_hidden=tuple(cfg["agent"]["encoder"].get("mlp_hidden", [128, 128, 128])),
            latent_dim=cfg["agent"]["encoder"].get("latent_dim", 128),
            dropout=cfg["agent"]["encoder"].get("dropout", 0.0),
        ),
        action_space_size=cfg["agent"]["policy"]["action_space_size"],
        learning_rate=cfg["training"]["learning_rate"],
        ppo_clip=cfg["training"]["ppo_clip"],
        cvar_beta=cfg["training"]["cvar_beta"],
        value_coef=cfg["training"]["value_coef"],
        entropy_coef=cfg["training"]["entropy_coef"],
        slack_coef=cfg["training"]["slack_coef"],
        grad_clip=cfg["training"]["grad_clip"],
        conformal_alpha=cfg["agent"]["conformal"]["alpha"],
    )
    agent = Agent(agent_cfg)
    log.info(f"Built agent: {sum(p.numel() for p in agent.parameters())} parameters")

    # Build environment
    rtl_path = args.design / "design.v"
    xdc_path = args.design / "constraints.xdc"
    if not rtl_path.exists():
        log.error(f"design RTL not found at {rtl_path}")
        return 1

    corners = [PVTCorner(**c) for c in cfg["environment"]["corners"]]
    env = Environment(
        rtl_path=rtl_path,
        device=cfg["environment"]["device"],
        constraints=xdc_path,
        tool=cfg["environment"]["tool"],
        tool_version=cfg["environment"]["tool_version"],
        seeds=list(range(1, cfg["environment"]["K_seeds"] + 1)),
        corners=corners,
        workdir=ensure_dir(args.output / "tool_runs"),
        parallel=cfg["environment"]["parallel"],
    )

    # Trainer
    trainer_cfg = TrainerConfig(
        episodes=args.episodes or cfg["training"]["episodes"],
        batch_size=cfg["training"]["batch_size"],
        rollouts_per_update=cfg["training"]["rollouts_per_update"],
        update_epochs=cfg["training"]["update_epochs"],
        validation_interval=cfg["training"]["validation_interval"],
        checkpoint_interval=cfg["training"]["checkpoint_interval"],
        calibration_interval=cfg["training"]["calibration_interval"],
        early_stop_patience=cfg["training"]["early_stop_patience"],
        output_dir=str(args.output),
    )

    trainer = Trainer(agent, env, trainer_cfg)
    log.info(f"Starting training: {trainer_cfg.episodes} episodes -> {args.output}")
    try:
        trainer.train()
    except NotImplementedError as e:
        log.warning(f"Toolchain rollouts unavailable: {e}")
        log.warning("Use scripts/run_simulator.py for simulator-driven training.")
        return 2
    log.info("Training complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
