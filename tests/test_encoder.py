"""Unit tests for robin_fpga.encoder."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from robin_fpga.encoder import Encoder, EncoderConfig, GATLayer, MultiHeadGAT


class TestGATLayer:
    def test_shape(self):
        layer = GATLayer(in_dim=16, out_dim=32)
        x = torch.randn(2, 10, 16)
        adj = torch.ones(2, 10, 10, dtype=torch.bool)
        y = layer(x, adj)
        assert y.shape == (2, 10, 32)

    def test_attention_respects_mask(self):
        """Disconnected nodes should not receive messages."""
        layer = GATLayer(in_dim=8, out_dim=8)
        x = torch.randn(1, 4, 8)
        adj = torch.eye(4, dtype=torch.bool).unsqueeze(0)
        y = layer(x, adj)
        assert y.shape == (1, 4, 8)
        assert not torch.isnan(y).any()


class TestMultiHeadGAT:
    def test_shape(self):
        m = MultiHeadGAT(in_dim=16, head_dim=8, num_heads=4)
        x = torch.randn(2, 10, 16)
        adj = torch.ones(2, 10, 10, dtype=torch.bool)
        y = m(x, adj)
        assert y.shape == (2, 10, 32)  # 4 heads * 8


class TestEncoder:
    def test_default_output_dim(self):
        enc = Encoder()
        assert enc.output_dim() == 128

    def test_forward_shape(self):
        enc = Encoder()
        B, N = 4, 12
        nf = torch.randn(B, N, enc.cfg.node_feat_dim)
        adj = torch.ones(B, N, N, dtype=torch.bool)
        tab = torch.randn(B, enc.cfg.tab_feat_dim)
        z = enc(nf, adj, tab)
        assert z.shape == (B, enc.cfg.latent_dim)

    def test_input_validation(self):
        enc = Encoder()
        with pytest.raises(ValueError):
            enc(torch.randn(10, 16), torch.ones(10, 10, dtype=torch.bool), torch.randn(10, 32))
        with pytest.raises(ValueError):
            enc(torch.randn(1, 10, 16), torch.ones(10, 10, dtype=torch.bool), torch.randn(1, 32))

    def test_gradient_flows(self):
        enc = Encoder()
        nf = torch.randn(2, 8, 16, requires_grad=True)
        adj = torch.ones(2, 8, 8, dtype=torch.bool)
        tab = torch.randn(2, 32, requires_grad=True)
        z = enc(nf, adj, tab)
        z.sum().backward()
        assert nf.grad is not None
        assert tab.grad is not None
