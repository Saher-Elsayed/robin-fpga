"""Categorical policy head π_θ(a|z) over directive bundles.

The action space is a Cartesian product of:
  * 4 strategy presets (Default, Performance_Explore, Congestion_SpreadLogic, Aggressive)
  * 3 phys-opt flags (off, default, aggressive)
  * 4 pblock variants (whole-die, quadrant, eighth, 16th)
  * 2 retiming modes (off, on)
  * 2 route-effort settings (default, high)

pruned to 192 feasible combinations. The policy outputs logits over this 192-dim
discrete action space; sampling is done with the Gumbel-Softmax trick during
training and argmax at evaluation.
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class Policy(nn.Module):
    """Categorical policy π_θ(a|z) over 192 directive bundles."""

    def __init__(
        self,
        latent_dim: int = 128,
        action_space_size: int = 192,
        hidden_dim: int = 128,
    ) -> None:
        super().__init__()
        self.latent_dim = latent_dim
        self.action_space_size = action_space_size

        self.head = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, action_space_size),
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """Compute action logits π(a|z) given latent state z.

        Parameters
        ----------
        z : torch.Tensor
            Latent state of shape (B, latent_dim).

        Returns
        -------
        torch.Tensor
            Logits of shape (B, action_space_size).
        """
        return self.head(z)

    def sample(self, z: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Sample an action and return (action_idx, log_prob)."""
        logits = self.forward(z)
        dist = torch.distributions.Categorical(logits=logits)
        action = dist.sample()
        log_prob = dist.log_prob(action)
        return action, log_prob

    def log_prob(self, z: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Evaluate the log-probability of a given action."""
        logits = self.forward(z)
        dist = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(action)

    def entropy(self, z: torch.Tensor) -> torch.Tensor:
        """Policy entropy H[π_θ(·|z)] for entropy bonus regularisation."""
        logits = self.forward(z)
        dist = torch.distributions.Categorical(logits=logits)
        return dist.entropy()

    def argmax(self, z: torch.Tensor) -> torch.Tensor:
        """Deterministic action (used at evaluation time)."""
        logits = self.forward(z)
        return logits.argmax(dim=-1)
