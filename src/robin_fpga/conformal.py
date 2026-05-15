"""Split-conformal predictor for calibrated FPGA timing sign-off.

This module implements the split-conformal procedure of Vovk, Gammerman, Shafer
(2005) applied to post-route Worst Negative Slack (WNS) prediction. The output
is a marginally-valid prediction interval that satisfies

    Pr[WNS in C_{1-alpha}(z)] >= 1 - alpha

under exchangeability of the calibration and test data. ROBIN-FPGA uses this
envelope as the sign-off criterion: a design is accepted iff the lower endpoint
of the envelope is non-negative.

References
----------
Vovk, Gammerman, Shafer. Algorithmic Learning in a Random World, Springer 2005.
Angelopoulos, Bates. "A Gentle Introduction to Conformal Prediction." 2023.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

# torch is optional; conformal works on numpy arrays or torch tensors
try:
    import torch
    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore
    _HAS_TORCH = False


@dataclass
class SignoffDecision:
    """Result of a conformal sign-off evaluation."""

    accepted: bool
    point_prediction: float            # \\widehat{WNS}(z)
    lower: float                       # lower endpoint of C_{1-alpha}
    upper: float                       # upper endpoint of C_{1-alpha}
    alpha: float                       # miscoverage target
    quantile: float                    # q_{1-alpha} (calibration quantile)
    calibration_size: int              # n in the split-conformal procedure
    audit_hash: str                    # SHA-256 of (weights, tool, seeds, corners)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


class ConformalSignoff:
    """Split-conformal predictor producing calibrated WNS envelopes.

    Workflow:
    1. Hold out a calibration set D_cal = {(z_i, WNS_i)} of post-route observations.
    2. Compute non-conformity scores e_i = |WNS_i - \\widehat{WNS}(z_i)|.
    3. Compute the (1-alpha)-quantile q of {e_i}.
    4. At test time, predict the envelope [\\widehat{WNS}(z) - q, \\widehat{WNS}(z) + q].
    5. Accept iff the lower endpoint is non-negative.

    Parameters
    ----------
    alpha : float
        Miscoverage target in (0, 1). Default 0.05 yields 95 percent envelopes.
    """

    def __init__(self, alpha: float = 0.05) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1); got {alpha}")
        self.alpha = alpha
        self._quantile: Optional[float] = None
        self._calibration_size: int = 0

    @classmethod
    def from_checkpoint(
        cls, path: str | Path, alpha: float = 0.05
    ) -> "ConformalSignoff":
        """Load a pre-fitted conformal predictor from disk."""
        instance = cls(alpha=alpha)
        if not _HAS_TORCH:
            raise ImportError("torch is required to load checkpoints")
        state = torch.load(path, map_location="cpu")
        if "conformal" not in state:
            raise KeyError(f"checkpoint {path} does not contain a 'conformal' key")
        cdata = state["conformal"]
        instance._quantile = float(cdata["quantile"])
        instance._calibration_size = int(cdata["calibration_size"])
        instance.alpha = float(cdata.get("alpha", alpha))
        return instance

    def calibrate(
        self,
        predictions: Any,
        observations: Any,
    ) -> None:
        """Fit the conformal quantile from a held-out calibration set.

        Parameters
        ----------
        predictions : tensor or array of shape (n,)
            Point predictions \\widehat{WNS}(z_i) from the slack-regression head.
        observations : tensor or array of shape (n,)
            Realised post-route WNS values WNS_i.
        """
        preds = np.asarray(predictions, dtype=float).flatten()
        obs = np.asarray(observations, dtype=float).flatten()

        if preds.shape != obs.shape:
            raise ValueError(
                f"predictions and observations must have the same shape; "
                f"got {preds.shape} vs {obs.shape}"
            )
        if preds.size < 10:
            raise ValueError(
                f"calibration set must contain at least 10 points; got {preds.size}"
            )

        n = preds.size
        residuals = np.abs(obs - preds)
        # Conformal quantile: ceil((n+1)*(1-alpha)) / n
        rank = math.ceil((n + 1) * (1.0 - self.alpha))
        rank = min(rank, n)
        sorted_residuals = np.sort(residuals)
        self._quantile = float(sorted_residuals[rank - 1])
        self._calibration_size = n

    @property
    def quantile(self) -> float:
        """The fitted conformal quantile q_{1-alpha}. Requires calibrate() first."""
        if self._quantile is None:
            raise RuntimeError("conformal predictor has not been calibrated yet")
        return self._quantile

    def envelope(self, prediction: float) -> tuple[float, float]:
        """Return the (lower, upper) endpoints of the conformal envelope.

        Parameters
        ----------
        prediction : float
            Point prediction \\widehat{WNS}(z) from the slack-regression head.
        """
        q = self.quantile
        return (prediction - q, prediction + q)

    def evaluate(
        self,
        prediction: float,
        audit_metadata: Optional[dict] = None,
    ) -> SignoffDecision:
        """Apply the sign-off rule: accept iff lower endpoint >= 0.

        Parameters
        ----------
        prediction : float
            Point prediction \\widehat{WNS}(z).
        audit_metadata : dict, optional
            Metadata to hash into the audit trail (tool version, seeds, corners,
            policy weight hash, etc.).
        """
        lower, upper = self.envelope(prediction)
        accepted = lower >= 0.0

        audit_hash = self._compute_audit_hash(prediction, audit_metadata or {})

        return SignoffDecision(
            accepted=accepted,
            point_prediction=float(prediction),
            lower=float(lower),
            upper=float(upper),
            alpha=self.alpha,
            quantile=self.quantile,
            calibration_size=self._calibration_size,
            audit_hash=audit_hash,
        )

    def empirical_coverage(
        self,
        predictions: Any,
        observations: Any,
    ) -> float:
        """Compute empirical coverage on a held-out test set."""
        preds = np.asarray(predictions, dtype=float).flatten()
        obs = np.asarray(observations, dtype=float).flatten()
        q = self.quantile
        in_envelope = (obs >= preds - q) & (obs <= preds + q)
        return float(in_envelope.mean())

    def _compute_audit_hash(self, prediction: float, metadata: dict) -> str:
        """Compute a deterministic SHA-256 hash of the sign-off context."""
        payload = {
            "prediction": prediction,
            "quantile": self.quantile,
            "alpha": self.alpha,
            "calibration_size": self._calibration_size,
            **metadata,
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()

    def state_dict(self) -> dict:
        """Serializable state for checkpointing."""
        if self._quantile is None:
            raise RuntimeError("cannot serialize an uncalibrated predictor")
        return {
            "quantile": self._quantile,
            "calibration_size": self._calibration_size,
            "alpha": self.alpha,
        }

    def load_state_dict(self, state: dict) -> None:
        self._quantile = float(state["quantile"])
        self._calibration_size = int(state["calibration_size"])
        self.alpha = float(state["alpha"])
