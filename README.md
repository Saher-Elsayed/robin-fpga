<div align="center">

# ROBIN-FPGA

**Distributionally-Robust Reinforcement Learning with Conformal Sign-off for FPGA Timing Closure**

[![CI](https://github.com/saher-elsayed/robin-fpga/actions/workflows/ci.yml/badge.svg)](https://github.com/saher-elsayed/robin-fpga/actions/workflows/ci.yml)
[![Docs](https://github.com/saher-elsayed/robin-fpga/actions/workflows/docs.yml/badge.svg)](https://saher-elsayed.github.io/robin-fpga/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.1+-EE4C2C.svg)](https://pytorch.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![arXiv](https://img.shields.io/badge/arXiv-2026.XXXXX-b31b1b.svg)](https://arxiv.org/abs/2026.XXXXX)

*An algorithm–toolchain co-designed framework for FPGA timing-closure design-space exploration with calibrated post-route uncertainty quantification.*

[**Paper**](paper/) • [**Documentation**](docs/) • [**Quickstart**](#quickstart) • [**Benchmarks**](#benchmarks) • [**Citation**](#citation)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Key Results](#key-results)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Quickstart](#quickstart)
6. [Repository Layout](#repository-layout)
7. [Benchmarks](#benchmarks)
8. [Reproducing the Paper](#reproducing-the-paper)
9. [Using ROBIN-FPGA on Your Own Designs](#using-robin-fpga-on-your-own-designs)
10. [Configuration](#configuration)
11. [Tcl Flows](#tcl-flows)
12. [Testing](#testing)
13. [Documentation](#documentation)
14. [Roadmap](#roadmap)
15. [Citation](#citation)
16. [Contributing](#contributing)
17. [License](#license)

---

## Overview

Modern FPGA timing closure is dominated by long, non-deterministic place-and-route (P\&R) iterations whose **Worst Negative Slack (WNS)** outcomes are highly sensitive to:

| Stochasticity source | Typical $\sigma(\text{WNS})$ on GEMM-systolic-16×16 |
|---|---|
| **Placer seed**             | $0.31$ ns (default), $0.45$ ns (aggressive) |
| **PVT corner choice**       | $\geq 0.1$ ns shifts across slow–fast corners |
| **Tool minor-version drift**| up to $5$–$7$ pp coverage degradation |

Existing machine-learning-for-EDA methods improve mean Quality-of-Results (QoR) but rarely characterise their own reliability under tool stochasticity, leaving designers without a statistical sign-off envelope.

**ROBIN-FPGA** is a framework that, in a single end-to-end pipeline, combines:

1. **A graph-attention encoder** over the post-synthesis timing graph with a tabular feature head for utilisation, congestion percentiles, tool-version, and device-family embedding.
2. **A Distributionally-Robust Proximal Policy Optimisation (DR-PPO) agent** that hedges against P\&R seed variance via a Conditional-Value-at-Risk (CVaR$_\beta$) shaped advantage estimator.
3. **A split-conformal predictor** that wraps the trained policy and produces a calibrated upper bound on residual WNS risk at user-specified confidence $1{-}\alpha$.

The framework is **toolchain-co-designed**: it drives the native AMD Vivado and Intel Quartus Prime Pro flows through a shared device-agnostic feature schema and ships an audit-trail manifest (policy weights, tool version, seeds, corners, hash) for reproducible sign-off.

---

## Key Results

On a **14-design benchmark** across six workload classes and two FPGA families (AMD Versal AI Edge VE2302, Intel Agilex 7 AGI 027):

| Metric                            | ROBIN-FPGA | Strongest baseline (DRiLLS-style) | Δ        |
|:----------------------------------|:----------:|:---------------------------------:|:--------:|
| Mean closure rate (% of K′=10 held-out seeds with WNS ≥ 0) | **89.8%** | 75.3%                              | **+14.5 pp** |
| Inter-seed σ(WNS), GEMM-systolic  | **0.12 ns** | 0.30 ns                            | **−2.5×**     |
| Empirical conformal coverage @ 1−α=0.95 (exchangeable) | **0.953** | n/a (no envelope)                  | calibrated   |
| Cross-family transfer cost (AMD → Intel, recovers 87%)  | **5%** of from-scratch GPU-h | 100%                              | **−20×**       |
| Dynamic power @ matched latency (GEMM, Pareto) | **−0.8 to −2.1 W** | (reference) | dominating frontier |

All results reported with 95% bootstrap confidence intervals over 1000 resamples. See [`paper/`](paper/) and [`data/results/`](data/results/) for full numerical results.

---

## Architecture

```
                    ROBIN-FPGA: end-to-end pipeline
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐
    │ (1)      │→ │ (2)      │→ │ (3)      │→ │ (4) MLP    │
    │ Timing   │  │ GAT-1    │  │ GAT-2    │  │ fusion zₜ  │
    │ graph Gₜ │  │ H=4 d=32 │  │ H=4 d=64 │  │ ∈ ℝ¹²⁸     │
    └──────────┘  └──────────┘  └──────────┘  └─────┬──────┘
                                        ┌───────────┘
                  ┌────────────┐  ┌─────▼────┐  ┌────────────┐
                  │ (5) Policy │  │ (6) Value│  │ (7) Conf.  │
                  │ π(a|z)     │  │ V_φ(z)   │  │ C_{1-α}    │
                  │ |A| = 192  │  │ scalar   │  │ envelope   │
                  └────────────┘  └──────────┘  └────────────┘
```

The DR-MDP training loop (Fig. 4 in the paper) is a clockwise 4-stage cycle:

```
   (1) DR-PPO agent    ───emit aₜ───▶     (2) FPGA env (K×|Θ|)
         ▲                                         │
         │                                         │ run, collect {R_{k,θ}}
   robust update θ_{t+1}                           ▼
         │                                  (3) Return dist + CVaR_β
   (4) DR-PPO update   ◀──compute CVaR_β + Â^β_t──┘
```

See [`docs/architecture.md`](docs/architecture.md) for the full technical specification.

---

## Installation

### Prerequisites

* **Python** 3.10 or newer
* **PyTorch** 2.1 or newer (CUDA 11.8 or 12.1 recommended for training)
* **Vivado** 2024.2 or newer (for AMD device targets) — *not bundled, install separately*
* **Quartus Prime Pro** 24.1 or newer (for Intel device targets) — *not bundled*
* **Linux** (Ubuntu 22.04 LTS recommended). macOS supported for development; tool integration is Linux-only.

### From source (recommended for development)

```bash
git clone https://github.com/saher-elsayed/robin-fpga.git
cd robin-fpga
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### From PyPI

```bash
pip install robin-fpga
```

### Using conda

```bash
conda env create -f environment.yml
conda activate robin-fpga
pip install -e .
```

### Verifying the install

```bash
robin-fpga --version
python -c "import robin_fpga; print(robin_fpga.__version__)"
pytest tests/ -v
```

See [`docs/installation.md`](docs/installation.md) for tool-side setup (Vivado/Quartus integration, license servers, GPU drivers).

---

## Quickstart

```bash
# 1. Generate all paper data
python scripts/run_simulator.py --output data/results/

# 2. Regenerate every figure in the paper
python scripts/generate_figures.py --data data/results/ --output figures/

# 3. Run unit tests
pytest tests/ -v
```

To run FPGA toolchain training (requires Vivado / Quartus):

```bash
# Train on GEMM-systolic, Versal AI Edge, 100 episodes
robin-fpga train \
  --config configs/versal.yaml \
  --design data/benchmarks/gemm_systolic_16x16/ \
  --episodes 100 \
  --output runs/gemm_versal_$(date +%Y%m%d)/
```

To evaluate a trained policy with conformal sign-off:

```bash
robin-fpga evaluate \
  --checkpoint runs/gemm_versal_20260515/best.pt \
  --design data/benchmarks/gemm_systolic_16x16/ \
  --alpha 0.05 \
  --seeds 10
```

The evaluation output prints the calibrated envelope $\mathcal{C}_{1-\alpha}$ and the accept/reject sign-off decision; the audit-trail manifest is written to `runs/<id>/audit.json`.

---

## Repository Layout

```
robin-fpga/
├── README.md                      ← this file
├── LICENSE                        ← MIT
├── CITATION.bib                   ← bibtex
├── pyproject.toml                 ← packaging (PEP 621)
├── requirements.txt               ← pinned dependencies
├── environment.yml                ← conda env
├── Makefile                       ← convenience targets
├── CHANGELOG.md                   ← versioned changelog
├── CONTRIBUTING.md                ← contribution guide
├── CODE_OF_CONDUCT.md             ← community standards
├── SECURITY.md                    ← responsible disclosure
│
├── src/robin_fpga/                ← Python package
│   ├── __init__.py
│   ├── __version__.py
│   ├── agent.py                   ← DR-PPO agent
│   ├── encoder.py                 ← GAT + MLP encoder
│   ├── policy.py                  ← policy head π_θ(a|z)
│   ├── value.py                   ← value head V_φ(z)
│   ├── cvar.py                    ← Conditional-Value-at-Risk
│   ├── conformal.py               ← split-conformal predictor
│   ├── environment.py             ← FPGA toolchain wrapper
│   ├── trainer.py                 ← training loop
│   ├── evaluator.py               ← evaluation + sign-off
│   ├── simulator.py               ← synthetic data generator
│   ├── data_loader.py             ← benchmark catalogue loader
│   └── utils.py                   ← logging, seeding, IO
│
├── flows/                         ← vendor Tcl scripts
│   ├── README.md
│   ├── vivado/
│   │   ├── synth.tcl
│   │   ├── place_route.tcl
│   │   ├── reports.tcl
│   │   └── strategies.xdc
│   └── quartus/
│       ├── synthesis.tcl
│       ├── fit.tcl
│       ├── sta.tcl
│       └── strategies.qsf
│
├── configs/                       ← YAML configurations
│   ├── default.yaml
│   ├── versal.yaml                ← AMD Versal AI Edge defaults
│   ├── agilex.yaml                ← Intel Agilex 7 defaults
│   ├── cvar_sweep.yaml            ← β sensitivity study
│   └── benchmarks.yaml            ← 14-design catalogue
│
├── scripts/                       ← CLI utilities
│   ├── train.py
│   ├── evaluate.py
│   ├── run_simulator.py
│   ├── generate_figures.py
│   ├── benchmark.sh
│   └── setup_env.sh
│
├── data/
│   ├── README.md
│   ├── benchmarks/
│   │   └── manifest.json
│   └── results/                   ← per-figure CSV data
│       ├── closure_rates.csv
│       ├── convergence.csv
│       ├── sigma_wns.csv
│       ├── transfer.csv
│       ├── coverage.csv
│       ├── pareto.csv
│       ├── per_design.csv
│       ├── class_breakdown.csv
│       ├── corner_wns.csv
│       ├── ablation.csv
│       ├── stress.csv
│       ├── hack_clip.csv
│       └── hack_noclip.csv
│
├── tests/                         ← pytest suite
│   ├── __init__.py
│   ├── test_cvar.py
│   ├── test_conformal.py
│   ├── test_agent.py
│   ├── test_encoder.py
│   └── test_environment.py
│
├── docs/                          ← user documentation
│   ├── architecture.md
│   ├── usage.md
│   ├── installation.md
│   ├── benchmarks.md
│   ├── reproduction.md
│   ├── troubleshooting.md
│   └── images/
│
├── notebooks/                     ← Jupyter walkthroughs
│   ├── 01_quickstart.ipynb
│   ├── 02_train_policy.ipynb
│   ├── 03_evaluation.ipynb
│   └── 04_figure_generation.ipynb
│
├── paper/                         ← LaTeX source + PDF
│   ├── README.md
│   ├── BUILD.md
│   ├── robin-fpga.tex
│   └── robin-fpga.pdf
│
└── .github/
    ├── workflows/
    │   ├── ci.yml                 ← lint + test + coverage
    │   ├── docs.yml               ← Sphinx → GitHub Pages
    │   └── publish.yml            ← PyPI release
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    ├── PULL_REQUEST_TEMPLATE.md
    └── dependabot.yml
```

---

## Benchmarks

The 14-design benchmark spans 6 workload classes:

| Class    | Designs                                      | Size range (LUTs) |
|:---------|:---------------------------------------------|:-----------------:|
| DSP      | FFT-1024 radix-4, FIR-256, BeamFormer-8, CORDIC | 24K – 95K        |
| AI       | GEMM-systolic-16×16, MobileNet-V2 layer, Attention-head | 110K – 380K |
| Graph    | BFS engine, PageRank                         | 45K – 70K        |
| Control  | PCIe Gen5 CSR, NoC arbiter, Crossbar         | 28K – 55K        |
| Sort     | Bitonic-1024                                 | 38K              |
| Crypto   | AES-128, SHA-3 Keccak-f[1600], NTT           | 32K – 88K        |

Of these, 10 are used for training, 2 for validation, and 2 are held out for in-family test. Full catalogue: [`data/benchmarks/manifest.json`](data/benchmarks/manifest.json).

---

## Reproducing the Paper

```bash
# 1. Set up environment
make install

# 2. Generate all data (simulator stand-in for the 4,900-run sweep)
make data

# 3. Regenerate all 18 figures
make figures

# 4. Build the PDF
make paper

# Equivalent to:
python scripts/run_simulator.py --seed 42 --output data/results/
python scripts/generate_figures.py --data data/results/ --output paper/figures/
cd paper && pdflatex robin-fpga.tex && pdflatex robin-fpga.tex
```

The simulator is calibrated to pilot statistics observed on GEMM-systolic and NoC-arbiter pilot runs and reproduces the qualitative effects predicted by the framework's contributions. See [`docs/reproduction.md`](docs/reproduction.md) for the full protocol, including how to swap in measured data once the 4,900-run cluster sweep completes.

---

## Using ROBIN-FPGA on Your Own Designs

```python
from robin_fpga import Agent, Environment, ConformalSignoff

# 1. Load a trained policy
agent = Agent.from_checkpoint("runs/best.pt")

# 2. Point at your design + device
env = Environment(
    rtl_path="path/to/your_design.v",
    device="xcve2302-sfva784-2MP-e-S",   # Versal AI Edge VE2302
    constraints="path/to/your_design.xdc",
    tool="vivado",
    tool_version="2024.2",
)

# 3. Run the closure loop
result = agent.close(env, episodes=50)

# 4. Apply the conformal envelope and decide accept/reject
signoff = ConformalSignoff.from_checkpoint("runs/best.pt", alpha=0.05)
decision = signoff.evaluate(result)

print(f"Accepted: {decision.accepted}")
print(f"Envelope: [{decision.lower:.3f}, {decision.upper:.3f}] ns")
print(f"Audit hash: {decision.audit_hash}")
```

The audit manifest is portable and reproducible: any later run with the same `(weights, tool_version, seeds, corners)` will produce a bit-exact closure.

---

## Configuration

All experiments are driven by YAML configurations in [`configs/`](configs/). Key fields:

```yaml
# configs/default.yaml (excerpt)
agent:
  encoder:
    gat_layers: 2
    gat_heads: 4
    hidden_dim: 64
    mlp_hidden: [128, 128, 128]
    mlp_activation: gelu
  policy:
    action_space_size: 192
  value:
    hidden_dim: 128
  conformal:
    alpha: 0.05
    calibration_size: 50

training:
  episodes: 1200
  batch_size: 64
  learning_rate: 3.0e-4
  ppo_clip: 0.2
  cvar_beta: 0.20
  value_coef: 0.5
  entropy_coef: 0.01
  slack_coef: 0.5

environment:
  K_seeds: 10
  corners:
    - { p: SS, v: nominal, t: 125 }
    - { p: TT, v: nominal, t: 25 }
    - { p: FF, v: nominal, t: -40 }
  wall_clock_budget_hours: 2

reward:
  w_wns: 1.0
  w_tns: 0.3
  kappa_util: 5.0
  kappa_fail: 10.0
  clip_wns: true     # critical for avoiding the pblock-shrink reward hack
```

Override any field via CLI flags or by composing configs:

```bash
robin-fpga train --config configs/versal.yaml --override training.cvar_beta=0.10
```

---

## Tcl Flows

The `flows/` directory contains the vendor-native Tcl scripts that the environment invokes. Each script is parameterised by environment variables set by `robin_fpga.environment`.

**AMD Vivado flow** (`flows/vivado/`):

```bash
vivado -mode batch -source flows/vivado/synth.tcl \
       -tclargs --rtl my_design.v --part xcve2302-sfva784-2MP-e-S \
                --strategy Performance_Explore
```

**Intel Quartus flow** (`flows/quartus/`):

```bash
quartus_sh -t flows/quartus/synthesis.tcl \
           --rtl my_design.v --part AGIB027R29A1E2VR0 \
           --strategy Performance_HighEffort
```

Both flows write reports into the canonical schema parsed by the device-agnostic feature normaliser (Fig. 5 in the paper).

---

## Testing

```bash
# Full test suite with coverage
pytest tests/ -v --cov=robin_fpga --cov-report=html

# Specific module
pytest tests/test_cvar.py -v

# Pre-commit hooks
pre-commit run --all-files
```

CI runs on every push: lint (`ruff` + `black`), type check (`mypy`), tests (`pytest`), coverage (≥ 85% required).

---

## Documentation

Full documentation is hosted at **<https://saher-elsayed.github.io/robin-fpga/>** and lives in [`docs/`](docs/):

* [Installation](docs/installation.md) — detailed setup including tool integration
* [Architecture](docs/architecture.md) — encoder, agent, conformal head specification
* [Usage](docs/usage.md) — CLI reference and Python API
* [Benchmarks](docs/benchmarks.md) — design suite, metrics, baselines
* [Reproduction](docs/reproduction.md) — paper-figure reproduction protocol
* [Troubleshooting](docs/troubleshooting.md) — common pitfalls and fixes

Live walkthroughs in [`notebooks/`](notebooks/):

1. **Quickstart** — load a checkpoint, run a single closure on a small design
2. **Train a policy from scratch** — full DR-PPO loop on GEMM-systolic
3. **Evaluation** — conformal sign-off, coverage diagnostics
4. **Figure generation** — reproduce every figure in the paper

---

## Roadmap

* **v0.2** — model-based RL variant (learned QoR surrogate) to reduce P\&R training cost
* **v0.3** — Lattice / Achronix / Microchip PolarFire device support
* **v0.4** — joint timing + power + area multi-objective optimisation
* **v0.5** — adaptive accelerator-mapping (AIE-ML ↔ PL operator placement)
* **v1.0** — production release with stability guarantees

See [issues](https://github.com/saher-elsayed/robin-fpga/issues) and [CHANGELOG.md](CHANGELOG.md).

---

## Citation

If you use ROBIN-FPGA in your research, please cite:

```bibtex
@article{elsayed2026robinfpga,
  title   = {{ROBIN-FPGA}: Distributionally-Robust Reinforcement Learning
             with Conformal Sign-off for {FPGA} Timing Closure},
  author  = {Elsayed, Saher},
  journal = {IEEE Transactions on Computer-Aided Design of Integrated
             Circuits and Systems},
  year    = {2026},
  note    = {Under review}
}
```

A bibtex file is also provided in [`CITATION.bib`](CITATION.bib).

---

## Contributing

Contributions are welcome! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request. By contributing, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

For security issues, see [`SECURITY.md`](SECURITY.md).

---

## License

This project is released under the MIT License — see [`LICENSE`](LICENSE) for the full text.

The 14-design benchmark suite includes designs derived from public sources; per-design license attributions are in [`data/benchmarks/manifest.json`](data/benchmarks/manifest.json).

Vivado and Quartus are trademarks of AMD and Intel respectively; ROBIN-FPGA is not affiliated with either vendor.

---

<div align="center">

*Maintained by [Saher Elsayed](https://github.com/saher-elsayed) — questions, ideas, bug reports → [open an issue](https://github.com/saher-elsayed/robin-fpga/issues).*

</div>
