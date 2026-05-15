"""Value head V_φ(z) and slack-regression head \\widehat{WNS}(z).

These two heads share the encoder backbone but are functionally distinct:
  * V_φ(z) estimates the expected discounted return; used as PPO baseline.
  * \\widehat{WNS}(z) estimates post-route WNS; feeds the conformal calibration set.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class Value(nn.Module):
    """Scalar value head V_φ(z) for PPO baseline."""

    def __init__(self, latent_dim: int = 128, hidden_dim: int = 128) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """Return V_φ(z) as a scalar per sample."""
        return self.net(z).squeeze(-1)


class SlackHead(nn.Module):
    """Slack-regression head \\widehat{WNS}(z) feeding the conformal calibration set."""

    def __init__(self, latent_dim: int = 128, hidden_dim: int = 64) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """Return \\widehat{WNS}(z) in nanoseconds (sign-preserving)."""
        return self.net(z).squeeze(-1)

    def huber_loss(
        self,
        z: torch.Tensor,
        target_wns: torch.Tensor,
        delta: float = 1.0,
    ) -> torch.Tensor:
        """Huber regression loss; robust to outliers in WNS."""
        pred = self.forward(z)
        return F.smooth_l1_loss(pred, target_wns, beta=delta)
