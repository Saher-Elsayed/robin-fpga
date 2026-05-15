"""DR-PPO training loop orchestrator.

Implements Algorithm 1 from the paper. Drives:
  * episode rollouts through the Environment
  * CVaR-shaped advantage computation
  * PPO updates on the Agent
  * periodic conformal recalibration
  * checkpointing + W&B / TensorBoard logging
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from robin_fpga.agent import Agent, AgentConfig
from robin_fpga.environment import Environment, returns_from_reports

log = logging.getLogger(__name__)


@dataclass
class TrainerConfig:
    """Top-level training configuration."""

    episodes: int = 1200
    batch_size: int = 64
    rollouts_per_update: int = 4
    update_epochs: int = 4
    validation_interval: int = 50
    checkpoint_interval: int = 100
    calibration_interval: int = 100
    calibration_size: int = 50
    early_stop_patience: int = 200
    output_dir: str = "./runs"
    log_level: str = "INFO"


class Trainer:
    """DR-PPO trainer.

    Example
    -------
    >>> trainer = Trainer(agent, env, TrainerConfig(episodes=500))
    >>> history = trainer.train()
    """

    def __init__(
        self,
        agent: Agent,
        env: Environment,
        config: Optional[TrainerConfig] = None,
    ) -> None:
        self.agent = agent
        self.env = env
        self.cfg = config or TrainerConfig()
        self.output_dir = Path(self.cfg.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history: list[dict] = []
        self._best_metric = -float("inf")
        self._patience = 0
        logging.basicConfig(level=self.cfg.log_level)

    def train(self) -> list[dict]:
        """Run the full training loop and return episode history."""
        log.info(f"Starting DR-PPO training: {self.cfg.episodes} episodes")
        slack_preds_buffer: list[float] = []
        slack_obs_buffer: list[float] = []

        for episode in range(1, self.cfg.episodes + 1):
            start = time.time()

            # Collect rollouts
            batch = self._collect_rollouts()

            # PPO update
            update_diagnostics = []
            for _ in range(self.cfg.update_epochs):
                diag = self.agent.update(batch)
                update_diagnostics.append(diag)

            # Aggregate diagnostics
            metrics = self._aggregate_diagnostics(update_diagnostics)
            metrics["episode"] = episode
            metrics["wall_clock_sec"] = time.time() - start
            metrics["mean_return"] = float(batch["return"].mean().item())
            self.history.append(metrics)

            # Buffer slack predictions/observations for conformal recalibration
            slack_preds_buffer.extend(batch["slack_pred"].tolist())
            slack_obs_buffer.extend(batch["wns_target"].tolist())

            # Periodic conformal recalibration
            if (
                episode % self.cfg.calibration_interval == 0
                and len(slack_preds_buffer) >= self.cfg.calibration_size
            ):
                preds = np.asarray(slack_preds_buffer[-self.cfg.calibration_size:])
                obs = np.asarray(slack_obs_buffer[-self.cfg.calibration_size:])
                self.agent.calibrate_conformal(
                    torch.from_numpy(preds), torch.from_numpy(obs)
                )
                log.info(f"[Ep {episode}] Conformal recalibrated: q={self.agent.conformal.quantile:.4f}")

            # Checkpoint
            if episode % self.cfg.checkpoint_interval == 0:
                ckpt = self.output_dir / f"checkpoint_{episode:06d}.pt"
                self.agent.save(ckpt)
                log.info(f"[Ep {episode}] Saved checkpoint to {ckpt}")

            # Early-stop on mean return plateau
            current = metrics["mean_return"]
            if current > self._best_metric + 1e-3:
                self._best_metric = current
                self._patience = 0
                self.agent.save(self.output_dir / "best.pt")
            else:
                self._patience += 1
                if self._patience >= self.cfg.early_stop_patience:
                    log.info(f"[Ep {episode}] Early stopping: no improvement for {self._patience} eps")
                    break

            if episode % 10 == 0:
                log.info(
                    f"[Ep {episode}] return={current:+.3f} "
                    f"loss={metrics['loss/total']:.3f} "
                    f"patience={self._patience}/{self.cfg.early_stop_patience}"
                )

        self._save_history()
        return self.history

    def _collect_rollouts(self) -> dict[str, torch.Tensor]:
        """Collect a batch of (state, action, return) tuples from the environment.

        For training, this is normally backed by `Environment.step()`. In this
        skeleton, the rollout buffer is filled by the caller; the simulator
        version is implemented in scripts/run_simulator.py.
        """
        # Placeholder: actual rollouts populated by Environment.step
        # Real implementation would loop over self.cfg.rollouts_per_update,
        # call agent.act(), env.step(), aggregate returns via returns_from_reports.
        raise NotImplementedError(
            "Rollout collection requires an active Environment with toolchain; "
            "use scripts/run_simulator.py for simulator-driven training."
        )

    def _aggregate_diagnostics(self, diagnostics: list[dict]) -> dict[str, float]:
        keys = diagnostics[0].keys()
        return {k: float(np.mean([d[k] for d in diagnostics])) for k in keys}

    def _save_history(self) -> None:
        with open(self.output_dir / "history.json", "w") as f:
            json.dump(self.history, f, indent=2)
        log.info(f"Saved training history to {self.output_dir/'history.json'}")
