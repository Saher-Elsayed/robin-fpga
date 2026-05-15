"""ROBIN-FPGA agent: encoder + policy + value + slack-regression + conformal sign-off.

This module assembles the full DR-PPO agent (Figure 3 of the paper) and provides
high-level methods for sampling actions, computing the CVaR-shaped advantage,
running PPO updates, and producing calibrated sign-off envelopes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.optim as optim

from robin_fpga.conformal import ConformalSignoff
from robin_fpga.cvar import cvar_advantage
from robin_fpga.encoder import Encoder, EncoderConfig
from robin_fpga.policy import Policy
from robin_fpga.value import SlackHead, Value


@dataclass
class AgentConfig:
    """Agent hyperparameters."""

    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    action_space_size: int = 192
    learning_rate: float = 3e-4
    ppo_clip: float = 0.2
    cvar_beta: float = 0.20
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    slack_coef: float = 0.5
    grad_clip: float = 1.0
    conformal_alpha: float = 0.05


class Agent(nn.Module):
    """The ROBIN-FPGA agent: encoder + three heads + conformal sign-off wrapper."""

    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        super().__init__()
        cfg = config or AgentConfig()
        self.cfg = cfg

        self.encoder = Encoder(cfg.encoder)
        latent_dim = self.encoder.output_dim()

        self.policy = Policy(latent_dim, cfg.action_space_size)
        self.value = Value(latent_dim)
        self.slack_head = SlackHead(latent_dim)
        self.conformal = ConformalSignoff(alpha=cfg.conformal_alpha)

        self.optimizer = optim.Adam(
            self.parameters(), lr=cfg.learning_rate, eps=1e-5
        )

    # ----- forward / inference -------------------------------------------------

    def forward(
        self,
        node_feats: torch.Tensor,
        adj: torch.Tensor,
        tab_feats: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Single forward pass producing logits, value, and slack prediction."""
        z = self.encoder(node_feats, adj, tab_feats)
        return {
            "z": z,
            "logits": self.policy(z),
            "value": self.value(z),
            "slack_pred": self.slack_head(z),
        }

    def act(
        self,
        node_feats: torch.Tensor,
        adj: torch.Tensor,
        tab_feats: torch.Tensor,
        deterministic: bool = False,
    ) -> dict[str, torch.Tensor]:
        """Sample (or argmax) an action and return diagnostics."""
        z = self.encoder(node_feats, adj, tab_feats)
        if deterministic:
            action = self.policy.argmax(z)
            log_prob = self.policy.log_prob(z, action)
        else:
            action, log_prob = self.policy.sample(z)
        return {
            "action": action,
            "log_prob": log_prob,
            "value": self.value(z),
            "slack_pred": self.slack_head(z),
        }

    # ----- PPO update ---------------------------------------------------------

    def update(self, batch: dict[str, torch.Tensor]) -> dict[str, float]:
        """One PPO update step with CVaR-shaped advantage.

        Expects a batch dictionary with:
            node_feats : (B, N, F)
            adj        : (B, N, N)
            tab_feats  : (B, T)
            action     : (B,) long
            old_log_prob : (B,)
            return     : (B,) -- per-seed returns aggregated externally
            wns_target : (B,) -- realised WNS for slack-head training

        Returns a dict of scalar diagnostics for logging.
        """
        z = self.encoder(batch["node_feats"], batch["adj"], batch["tab_feats"])
        logits = self.policy(z)
        value = self.value(z)
        slack_pred = self.slack_head(z)

        dist = torch.distributions.Categorical(logits=logits)
        new_log_prob = dist.log_prob(batch["action"])
        entropy = dist.entropy().mean()

        # CVaR-shaped advantage
        advantages = cvar_advantage(
            batch["return"], value.detach(), beta=self.cfg.cvar_beta, normalize=True
        )

        # PPO clipped surrogate
        ratio = torch.exp(new_log_prob - batch["old_log_prob"])
        clipped_ratio = torch.clamp(
            ratio, 1.0 - self.cfg.ppo_clip, 1.0 + self.cfg.ppo_clip
        )
        policy_loss = -torch.min(ratio * advantages, clipped_ratio * advantages).mean()

        # Value loss (Huber)
        value_loss = torch.nn.functional.smooth_l1_loss(value, batch["return"])

        # Slack-head loss
        slack_loss = torch.nn.functional.smooth_l1_loss(slack_pred, batch["wns_target"])

        # Combined
        loss = (
            policy_loss
            + self.cfg.value_coef * value_loss
            - self.cfg.entropy_coef * entropy
            + self.cfg.slack_coef * slack_loss
        )

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.parameters(), self.cfg.grad_clip)
        self.optimizer.step()

        return {
            "loss/total": float(loss.item()),
            "loss/policy": float(policy_loss.item()),
            "loss/value": float(value_loss.item()),
            "loss/slack": float(slack_loss.item()),
            "loss/entropy": float(entropy.item()),
            "ppo/ratio_mean": float(ratio.mean().item()),
            "ppo/advantage_mean": float(advantages.mean().item()),
            "ppo/advantage_std": float(advantages.std().item()),
        }

    # ----- sign-off ------------------------------------------------------------

    def calibrate_conformal(
        self,
        slack_preds: torch.Tensor,
        slack_obs: torch.Tensor,
    ) -> None:
        """Calibrate the conformal envelope from a held-out batch."""
        self.conformal.calibrate(slack_preds, slack_obs)

    def signoff(
        self,
        node_feats: torch.Tensor,
        adj: torch.Tensor,
        tab_feats: torch.Tensor,
        audit_metadata: Optional[dict] = None,
    ):
        """Run the calibrated sign-off on a single (or batched) state.

        Returns a SignoffDecision for each sample.
        """
        self.eval()
        with torch.no_grad():
            z = self.encoder(node_feats, adj, tab_feats)
            slack_pred = self.slack_head(z)
        decisions = []
        for i in range(slack_pred.shape[0]):
            metadata = (audit_metadata or {}).copy()
            metadata["weights_hash"] = self._weights_hash()
            decisions.append(
                self.conformal.evaluate(float(slack_pred[i].item()), metadata)
            )
        return decisions

    # ----- (de)serialisation --------------------------------------------------

    def save(self, path: str | Path) -> None:
        state = {
            "model": self.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "config": self.cfg.__dict__,
            "conformal": self.conformal.state_dict() if self.conformal._quantile else None,
        }
        torch.save(state, path)

    @classmethod
    def from_checkpoint(cls, path: str | Path) -> "Agent":
        state = torch.load(path, map_location="cpu")
        cfg = AgentConfig(**state.get("config", {})) if isinstance(state.get("config"), dict) else AgentConfig()
        agent = cls(cfg)
        agent.load_state_dict(state["model"])
        if state.get("conformal"):
            agent.conformal.load_state_dict(state["conformal"])
        return agent

    def _weights_hash(self) -> str:
        """SHA-256 hash of the policy weights for audit-trail integrity."""
        hasher = hashlib.sha256()
        for name, param in sorted(self.state_dict().items()):
            hasher.update(name.encode("utf-8"))
            hasher.update(param.cpu().numpy().tobytes())
        return hasher.hexdigest()
