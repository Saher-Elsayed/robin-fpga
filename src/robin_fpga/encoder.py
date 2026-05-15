"""Graph-attention + tabular feature encoder producing the latent state z_t.

The encoder consumes:
  * a post-synthesis timing graph G_t = (V, E) with node features
        {slack, capacitance, fanout, level, cell-type-onehot}
    and edge features
        {wirelength-est, net-fanout}
  * a tabular feature vector x_t in R^32 with
        {U_LUT, U_FF, U_BRAM, U_DSP, U_URAM, cong_pct, tool_ver, device_fam}

It produces a 128-dim latent state z_t consumed by the policy, value, and
conformal-regression heads (Figure 3 of the paper).

Architecture:
    G_t  -->  GAT_1 (H=4, d=32)  -->  GAT_2 (H=4, d=64)  -->  h^G_t
    x_t  -->  Linear -->  x_t'
    z_t  =  MLP_3layer( concat( h^G_t, x_t' ) ),  GELU activations
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class EncoderConfig:
    """Encoder hyperparameters."""

    node_feat_dim: int = 16          # slack, cap, fanout, level, cell-type onehot (~12)
    edge_feat_dim: int = 4           # wirelength-est, net-fanout, + 2 reserved
    tab_feat_dim: int = 32           # tabular feature vector size
    gat_heads: int = 4
    gat_hidden_1: int = 32
    gat_hidden_2: int = 64
    mlp_hidden: tuple[int, ...] = (128, 128, 128)
    latent_dim: int = 128
    dropout: float = 0.0


class GATLayer(nn.Module):
    """Single-head graph attention layer (Velickovic et al., ICLR 2018).

    Computes per-edge attention coefficients alpha_ij from concatenated node
    representations, then aggregates messages weighted by alpha. Multi-head
    extension stacks H of these in parallel and concatenates outputs.
    """

    def __init__(self, in_dim: int, out_dim: int) -> None:
        super().__init__()
        self.W = nn.Linear(in_dim, out_dim, bias=False)
        self.attn = nn.Linear(2 * out_dim, 1, bias=False)
        nn.init.xavier_uniform_(self.W.weight)
        nn.init.xavier_uniform_(self.attn.weight)

    def forward(
        self,
        node_feats: torch.Tensor,        # (B, N, in_dim)
        adj: torch.Tensor,                # (B, N, N) boolean adjacency
    ) -> torch.Tensor:
        B, N, _ = node_feats.shape
        h = self.W(node_feats)            # (B, N, out)
        # pairwise attention scores
        h_src = h.unsqueeze(2).expand(-1, -1, N, -1)
        h_dst = h.unsqueeze(1).expand(-1, N, -1, -1)
        pair = torch.cat([h_src, h_dst], dim=-1)
        e = F.leaky_relu(self.attn(pair).squeeze(-1), negative_slope=0.2)
        # mask non-edges
        e = e.masked_fill(~adj, float("-inf"))
        alpha = F.softmax(e, dim=-1)
        # aggregate
        return torch.bmm(alpha, h)


class MultiHeadGAT(nn.Module):
    """Multi-head GAT: H parallel heads with output concatenation."""

    def __init__(self, in_dim: int, head_dim: int, num_heads: int) -> None:
        super().__init__()
        self.heads = nn.ModuleList(
            [GATLayer(in_dim, head_dim) for _ in range(num_heads)]
        )

    def forward(self, node_feats: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        out = torch.cat([h(node_feats, adj) for h in self.heads], dim=-1)
        return F.elu(out)


class Encoder(nn.Module):
    """GAT + MLP fusion encoder producing the latent state z_t.

    The forward pass implements the four encoder stages of Figure 3:
        (1) input timing graph G_t
        (2) GAT layer 1 (H=4, d=32)
        (3) GAT layer 2 (H=4, d=64) -> graph embedding h^G_t in R^64
        (4) MLP fusion of (h^G_t, x_t) -> latent z_t in R^128
    """

    def __init__(self, config: Optional[EncoderConfig] = None) -> None:
        super().__init__()
        cfg = config or EncoderConfig()
        self.cfg = cfg

        # GAT layers
        self.gat1 = MultiHeadGAT(
            in_dim=cfg.node_feat_dim,
            head_dim=cfg.gat_hidden_1,
            num_heads=cfg.gat_heads,
        )
        gat1_out_dim = cfg.gat_hidden_1 * cfg.gat_heads
        self.gat2 = MultiHeadGAT(
            in_dim=gat1_out_dim,
            head_dim=cfg.gat_hidden_2,
            num_heads=cfg.gat_heads,
        )
        gat2_out_dim = cfg.gat_hidden_2 * cfg.gat_heads

        # Graph readout: mean + max pool, then project to fixed 64-dim
        self.graph_proj = nn.Linear(2 * gat2_out_dim, 64)

        # Tabular projection
        self.tab_proj = nn.Sequential(
            nn.Linear(cfg.tab_feat_dim, 64),
            nn.GELU(),
        )

        # Fusion MLP: 3 layers with GELU activations, dropout optional
        fusion_in = 64 + 64  # graph_emb + tab_emb
        layers: list[nn.Module] = []
        prev = fusion_in
        for h in cfg.mlp_hidden:
            layers += [nn.Linear(prev, h), nn.GELU()]
            if cfg.dropout > 0:
                layers.append(nn.Dropout(cfg.dropout))
            prev = h
        layers.append(nn.Linear(prev, cfg.latent_dim))
        self.mlp = nn.Sequential(*layers)

    def forward(
        self,
        node_feats: torch.Tensor,         # (B, N, node_feat_dim)
        adj: torch.Tensor,                 # (B, N, N) boolean
        tab_feats: torch.Tensor,           # (B, tab_feat_dim)
    ) -> torch.Tensor:
        """Encode a batch of (timing graph, tabular features) pairs into z_t."""
        if node_feats.dim() != 3:
            raise ValueError(f"node_feats must be (B,N,F); got {tuple(node_feats.shape)}")
        if adj.dim() != 3:
            raise ValueError(f"adj must be (B,N,N); got {tuple(adj.shape)}")
        if tab_feats.dim() != 2:
            raise ValueError(f"tab_feats must be (B,F); got {tuple(tab_feats.shape)}")

        # GAT stack
        h = self.gat1(node_feats, adj)
        h = self.gat2(h, adj)

        # Readout via mean + max pool
        graph_mean = h.mean(dim=1)
        graph_max = h.max(dim=1).values
        graph_emb = self.graph_proj(torch.cat([graph_mean, graph_max], dim=-1))

        # Tabular branch
        tab_emb = self.tab_proj(tab_feats)

        # Concat + fuse
        z = self.mlp(torch.cat([graph_emb, tab_emb], dim=-1))
        return z

    def output_dim(self) -> int:
        return self.cfg.latent_dim
