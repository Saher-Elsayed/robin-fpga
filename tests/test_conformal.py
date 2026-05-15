"""Unit tests for robin_fpga.conformal."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from robin_fpga.conformal import ConformalSignoff, SignoffDecision


class TestCalibration:
    def test_calibrate_basic(self):
        np.random.seed(0)
        preds = np.random.randn(200)
        obs = preds + np.random.randn(200) * 0.1
        pred_sig = ConformalSignoff(alpha=0.05)
        pred_sig.calibrate(preds, obs)
        assert pred_sig.quantile > 0

    def test_calibrate_quantile_grows_with_noise(self):
        np.random.seed(0)
        preds = np.zeros(200)
        for sigma in (0.1, 0.3, 1.0):
            obs = np.random.randn(200) * sigma
            pred_sig = ConformalSignoff(alpha=0.05)
            pred_sig.calibrate(preds, obs)
            # higher sigma -> wider envelope
            assert pred_sig.quantile > 0
            assert pred_sig.quantile < 10 * sigma

    def test_calibrate_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            ConformalSignoff().calibrate(np.zeros(10), np.zeros(5))

    def test_calibrate_too_few_samples_raises(self):
        with pytest.raises(ValueError):
            ConformalSignoff().calibrate(np.zeros(5), np.zeros(5))

    def test_invalid_alpha_raises(self):
        with pytest.raises(ValueError):
            ConformalSignoff(alpha=0.0)
        with pytest.raises(ValueError):
            ConformalSignoff(alpha=1.0)


class TestEnvelope:
    def test_envelope_symmetric(self):
        pred_sig = ConformalSignoff(alpha=0.05)
        pred_sig.calibrate(np.zeros(100), np.random.randn(100))
        lo, hi = pred_sig.envelope(0.5)
        q = pred_sig.quantile
        assert math.isclose(hi - 0.5, q, rel_tol=1e-6)
        assert math.isclose(0.5 - lo, q, rel_tol=1e-6)

    def test_envelope_requires_calibration(self):
        with pytest.raises(RuntimeError):
            ConformalSignoff().envelope(0.0)


class TestSignoffDecision:
    def test_accept_when_lower_nonneg(self):
        np.random.seed(0)
        pred_sig = ConformalSignoff(alpha=0.05)
        pred_sig.calibrate(np.zeros(100), np.random.randn(100) * 0.05)
        d = pred_sig.evaluate(prediction=0.5)
        assert isinstance(d, SignoffDecision)
        assert d.accepted is True
        assert d.lower >= 0.0

    def test_reject_when_lower_negative(self):
        np.random.seed(0)
        pred_sig = ConformalSignoff(alpha=0.05)
        pred_sig.calibrate(np.zeros(100), np.random.randn(100) * 0.5)
        d = pred_sig.evaluate(prediction=-0.1)
        assert d.accepted is False

    def test_audit_hash_deterministic(self):
        np.random.seed(0)
        pred_sig = ConformalSignoff(alpha=0.05)
        pred_sig.calibrate(np.zeros(100), np.random.randn(100) * 0.1)
        d1 = pred_sig.evaluate(prediction=0.0, audit_metadata={"tool": "vivado"})
        d2 = pred_sig.evaluate(prediction=0.0, audit_metadata={"tool": "vivado"})
        assert d1.audit_hash == d2.audit_hash

    def test_audit_hash_changes_with_metadata(self):
        np.random.seed(0)
        pred_sig = ConformalSignoff(alpha=0.05)
        pred_sig.calibrate(np.zeros(100), np.random.randn(100) * 0.1)
        d1 = pred_sig.evaluate(prediction=0.0, audit_metadata={"tool": "vivado"})
        d2 = pred_sig.evaluate(prediction=0.0, audit_metadata={"tool": "quartus"})
        assert d1.audit_hash != d2.audit_hash


class TestCoverage:
    def test_empirical_coverage_close_to_target(self):
        np.random.seed(42)
        cal_preds = np.random.randn(500)
        cal_obs = cal_preds + np.random.randn(500) * 0.1
        pred_sig = ConformalSignoff(alpha=0.10)
        pred_sig.calibrate(cal_preds, cal_obs)

        test_preds = np.random.randn(2000)
        test_obs = test_preds + np.random.randn(2000) * 0.1
        coverage = pred_sig.empirical_coverage(test_preds, test_obs)
        assert 0.88 <= coverage <= 0.95   # target = 0.90, tolerance


class TestSerialization:
    def test_state_dict_roundtrip(self):
        np.random.seed(0)
        a = ConformalSignoff(alpha=0.05)
        a.calibrate(np.zeros(100), np.random.randn(100) * 0.1)
        state = a.state_dict()

        b = ConformalSignoff()
        b.load_state_dict(state)
        assert b.quantile == a.quantile
        assert b.alpha == a.alpha

    def test_state_dict_requires_calibration(self):
        with pytest.raises(RuntimeError):
            ConformalSignoff().state_dict()


class TestSignoffSaveLoad:
    def test_save_to_json(self, tmp_path: Path):
        np.random.seed(0)
        pred_sig = ConformalSignoff(alpha=0.05)
        pred_sig.calibrate(np.zeros(100), np.random.randn(100) * 0.1)
        d = pred_sig.evaluate(prediction=0.5)
        out = tmp_path / "decision.json"
        d.save(out)
        assert out.exists()
        import json
        with open(out) as f:
            loaded = json.load(f)
        assert loaded["accepted"] == d.accepted
        assert loaded["audit_hash"] == d.audit_hash
