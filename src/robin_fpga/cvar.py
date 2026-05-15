"""Conditional Value-at-Risk (CVaR) for robust policy gradient.

The CVaR_beta of a random variable R is the conditional expectation of R given that
R falls in its lower-beta tail:

    CVaR_beta(R) := E[ R | R <= VaR_beta(R) ]

where VaR_beta(R) is the beta-quantile of R. This module provides:

* `var(returns, beta)`         — empirical Value-at-Risk
* `cvar(returns, beta)`        — empirical Conditional-Value-at-Risk
* `cvar_advantage(R, V, beta)` — CVaR-shaped advantage estimator for PPO
* `cvar_grad_estimator`        — Tamar et al. (2015) unbiased CVaR gradient

References
----------
Tamar, Glassner, Mannor. "Optimizing the CVaR via Sampling." AAAI 2015.
Rockafellar, Uryasev. "Optimization of Conditional Value-at-Risk." J. Risk 2000.
"""

from __future__ import annotations

import math
from typing import Optional

import torch


def var(returns: torch.Tensor, beta: float = 0.2) -> torch.Tensor:
    """Empirical Value-at-Risk at confidence level beta (lower tail).

    Parameters
    ----------
    returns : torch.Tensor
        1-D tensor of sampled returns.
    beta : float
        Tail-mass parameter in (0, 1). beta=0.2 means the worst 20 percent of returns
        define the VaR threshold.

    Returns
    -------
    torch.Tensor
        Scalar VaR_beta(R) computed as the beta-quantile of `returns`.
    """
    if not 0.0 < beta < 1.0:
        raise ValueError(f"beta must be in (0, 1); got {beta}")
    if returns.dim() != 1:
        raise ValueError(f"returns must be 1-D; got shape {tuple(returns.shape)}")
    if returns.numel() == 0:
        raise ValueError("returns must be non-empty")
    return torch.quantile(returns, beta, interpolation="linear")


def cvar(returns: torch.Tensor, beta: float = 0.2) -> torch.Tensor:
    """Empirical Conditional Value-at-Risk at level beta (lower tail).

    Defined as the average of all sample returns that fall at or below VaR_beta(R).
    A coherent risk measure (Artzner et al., 1999); replacing the mean by CVaR in a
    policy-gradient estimator yields the gradient direction that improves the
    lower-tail of the return distribution.

    Parameters
    ----------
    returns : torch.Tensor
        1-D tensor of sampled returns.
    beta : float
        Tail-mass parameter in (0, 1).

    Returns
    -------
    torch.Tensor
        Scalar CVaR_beta(R).
    """
    if not 0.0 < beta < 1.0:
        raise ValueError(f"beta must be in (0, 1); got {beta}")
    if returns.dim() != 1:
        raise ValueError(f"returns must be 1-D; got shape {tuple(returns.shape)}")
    if returns.numel() == 0:
        raise ValueError("returns must be non-empty")

    threshold = var(returns, beta)
    tail_mask = returns <= threshold
    if not tail_mask.any():
        # Numerical edge case: take the minimum
        return returns.min()
    return returns[tail_mask].mean()


def cvar_advantage(
    returns: torch.Tensor,
    values: torch.Tensor,
    beta: float = 0.2,
    normalize: bool = True,
    eps: float = 1e-8,
) -> torch.Tensor:
    """CVaR-shaped advantage estimator for PPO.

    Computes the CVaR-baseline advantage by substituting CVaR for the empirical mean
    in the standard advantage estimator. This is the key robustness-injection point
    of ROBIN-FPGA (Section IV-B of the paper).

    Parameters
    ----------
    returns : torch.Tensor
        Per-sample returns of shape (N,).
    values : torch.Tensor
        Per-sample value estimates V_phi(z_t) of shape (N,).
    beta : float
        CVaR tail-mass parameter.
    normalize : bool
        If True, normalize advantages to zero mean and unit variance (PPO convention).
    eps : float
        Numerical stability constant for normalization.

    Returns
    -------
    torch.Tensor
        Advantages of shape (N,) computed as A_t = CVaR_beta({R_k}) - V_phi(z_t).
    """
    if returns.shape != values.shape:
        raise ValueError(
            f"returns and values must have the same shape; "
            f"got {tuple(returns.shape)} vs {tuple(values.shape)}"
        )

    risk_baseline = cvar(returns, beta)
    advantages = risk_baseline - values

    if normalize:
        advantages = (advantages - advantages.mean()) / (advantages.std() + eps)

    return advantages


def cvar_grad_estimator(
    returns: torch.Tensor,
    log_probs: torch.Tensor,
    beta: float = 0.2,
) -> torch.Tensor:
    """Unbiased CVaR gradient estimator (Tamar et al., AAAI 2015).

    Computes the policy gradient under a CVaR objective. Only samples that lie in
    the lower-beta tail contribute to the gradient; their contributions are scaled
    by (1/beta).

    Parameters
    ----------
    returns : torch.Tensor
        Per-sample returns of shape (N,).
    log_probs : torch.Tensor
        Log-probabilities under the current policy, shape (N,).
    beta : float
        Tail-mass parameter.

    Returns
    -------
    torch.Tensor
        Scalar CVaR gradient surrogate.
    """
    threshold = var(returns, beta)
    tail_mask = (returns <= threshold).float()
    return -(1.0 / beta) * (tail_mask * (returns - threshold) * log_probs).mean()


def cvar_sensitivity_table(
    returns: torch.Tensor,
    betas: tuple[float, ...] = (0.05, 0.10, 0.20, 0.30, 0.50),
) -> dict[float, float]:
    """CVaR sweep across beta values, for sensitivity diagnostics.

    Useful for the beta-sensitivity ablation (Section VIII of the paper).
    """
    return {b: float(cvar(returns, b)) for b in betas}
