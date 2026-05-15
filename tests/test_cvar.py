"""Unit tests for robin_fpga.cvar."""

from __future__ import annotations

import math

import pytest
import torch

from robin_fpga.cvar import (
    cvar,
    cvar_advantage,
    cvar_grad_estimator,
    cvar_sensitivity_table,
    var,
)


class TestVaR:
    def test_var_uniform_distribution(self):
        """VaR_0.2 of Uniform[0, 1] should be approximately 0.2."""
        torch.manual_seed(42)
        x = torch.rand(10000)
        v = var(x, beta=0.2)
        assert abs(float(v) - 0.2) < 0.02

    def test_var_normal_distribution(self):
        """VaR_0.05 of N(0,1) should be approximately -1.645."""
        torch.manual_seed(42)
        x = torch.randn(50000)
        v = var(x, beta=0.05)
        assert abs(float(v) - (-1.645)) < 0.05

    def test_var_invalid_beta(self):
        x = torch.rand(100)
        with pytest.raises(ValueError):
            var(x, beta=0.0)
        with pytest.raises(ValueError):
            var(x, beta=1.0)
        with pytest.raises(ValueError):
            var(x, beta=-0.1)

    def test_var_empty_input(self):
        x = torch.empty(0)
        with pytest.raises(ValueError):
            var(x)


class TestCVaR:
    def test_cvar_uniform_distribution(self):
        """CVaR_0.2 of Uniform[0, 1] is the mean of [0, 0.2] = 0.1."""
        torch.manual_seed(42)
        x = torch.rand(10000)
        c = cvar(x, beta=0.2)
        assert abs(float(c) - 0.1) < 0.02

    def test_cvar_less_than_var(self):
        """CVaR_beta <= VaR_beta always."""
        torch.manual_seed(42)
        x = torch.randn(5000)
        for b in (0.05, 0.1, 0.2, 0.3):
            assert float(cvar(x, b)) <= float(var(x, b)) + 1e-6

    def test_cvar_monotone_in_beta(self):
        """CVaR is non-decreasing in beta."""
        torch.manual_seed(42)
        x = torch.randn(5000)
        cvars = [float(cvar(x, b)) for b in (0.05, 0.1, 0.2, 0.3, 0.5)]
        for a, b in zip(cvars, cvars[1:]):
            assert a <= b + 1e-6

    def test_cvar_degenerate_distribution(self):
        """CVaR of a constant equals that constant."""
        x = torch.full((1000,), 3.7)
        assert abs(float(cvar(x, 0.2)) - 3.7) < 1e-6


class TestCVaRAdvantage:
    def test_advantage_shape(self):
        torch.manual_seed(0)
        R = torch.randn(64)
        V = torch.randn(64)
        A = cvar_advantage(R, V, beta=0.2)
        assert A.shape == R.shape

    def test_advantage_normalization(self):
        torch.manual_seed(0)
        R = torch.randn(1000) * 5 + 2
        V = torch.randn(1000)
        A = cvar_advantage(R, V, beta=0.2, normalize=True)
        assert abs(float(A.mean())) < 1e-3
        assert abs(float(A.std()) - 1.0) < 1e-2

    def test_advantage_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            cvar_advantage(torch.zeros(10), torch.zeros(5))


class TestCVaRGradEstimator:
    def test_gradient_is_scalar(self):
        torch.manual_seed(0)
        R = torch.randn(100)
        lp = torch.randn(100)
        g = cvar_grad_estimator(R, lp, beta=0.2)
        assert g.shape == torch.Size([])

    def test_gradient_uses_lower_tail_only(self):
        """Gradient with all-positive returns and tight beta should be small."""
        R = torch.ones(100) * 2.0
        lp = torch.randn(100)
        g = cvar_grad_estimator(R, lp, beta=0.05)
        assert abs(float(g)) < 1.0


class TestSensitivityTable:
    def test_sensitivity_table_keys(self):
        torch.manual_seed(0)
        R = torch.randn(500)
        tbl = cvar_sensitivity_table(R, betas=(0.05, 0.1, 0.2))
        assert set(tbl.keys()) == {0.05, 0.1, 0.2}
        assert all(isinstance(v, float) for v in tbl.values())
