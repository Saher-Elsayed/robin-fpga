"""Unit tests for robin_fpga.agent (mostly smoke tests requiring torch)."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from robin_fpga.agent import Agent, AgentConfig
from robin_fpga.encoder import EncoderConfig


def _make_batch(B: int = 4, N: int = 8, F: int = 16, T: int = 32) -> dict:
    """Construct a synthetic batch shaped like the encoder expects."""
    return {
        "node_feats": torch.randn(B, N, F),
        "adj": torch.ones(B, N, N, dtype=torch.bool),
        "tab_feats": torch.randn(B, T),
        "action": torch.randint(0, 192, (B,)),
        "old_log_prob": torch.randn(B),
        "return": torch.randn(B),
        "wns_target": torch.randn(B),
    }


class TestAgentInstantiation:
    def test_default_construction(self):
        agent = Agent()
        assert agent.policy.action_space_size == 192
        assert agent.cfg.cvar_beta == 0.20

    def test_parameter_count_reasonable(self):
        agent = Agent()
        n = sum(p.numel() for p in agent.parameters())
        assert 1e5 < n < 1e7  # something between 100K and 10M params


class TestAgentForward:
    def test_forward_shapes(self):
        agent = Agent()
        agent.eval()
        with torch.no_grad():
            out = agent.forward(*_test_inputs())
        B = _test_inputs()[0].shape[0]
        assert out["z"].shape == (B, agent.cfg.encoder.latent_dim)
        assert out["logits"].shape == (B, agent.cfg.action_space_size)
        assert out["value"].shape == (B,)
        assert out["slack_pred"].shape == (B,)

    def test_act_returns_valid_actions(self):
        agent = Agent()
        agent.eval()
        with torch.no_grad():
            out = agent.act(*_test_inputs())
        assert out["action"].dtype == torch.int64
        assert torch.all(out["action"] >= 0)
        assert torch.all(out["action"] < agent.cfg.action_space_size)

    def test_act_deterministic(self):
        agent = Agent()
        agent.eval()
        with torch.no_grad():
            out1 = agent.act(*_test_inputs(), deterministic=True)
            out2 = agent.act(*_test_inputs(), deterministic=True)
        assert torch.equal(out1["action"], out2["action"])


class TestAgentUpdate:
    def test_update_returns_diagnostics(self):
        agent = Agent()
        batch = _make_batch()
        diag = agent.update(batch)
        for key in ("loss/total", "loss/policy", "loss/value", "loss/slack"):
            assert key in diag
            assert isinstance(diag[key], float)


class TestAgentSerialization:
    def test_save_and_load(self, tmp_path):
        agent = Agent()
        ckpt = tmp_path / "test.pt"
        agent.save(ckpt)
        assert ckpt.exists()
        loaded = Agent.from_checkpoint(ckpt)
        # quick equality on state dicts
        sd1 = agent.state_dict()
        sd2 = loaded.state_dict()
        for k in sd1:
            assert torch.allclose(sd1[k], sd2[k])


# --- helpers ----

def _test_inputs():
    B, N, F, T = 4, 8, 16, 32
    return (
        torch.randn(B, N, F),
        torch.ones(B, N, N, dtype=torch.bool),
        torch.randn(B, T),
    )
