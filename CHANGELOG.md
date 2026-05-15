# Changelog

All notable changes to ROBIN-FPGA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Model-based RL variant with learned QoR surrogate (work in progress)
- Hyperparameter sensitivity sweep tooling under `scripts/sweep.py`

### Changed
- Updated benchmark catalogue with two additional graph-workload designs

## [0.1.0] - 2026-05-15

Initial public release accompanying the IEEE TCAD paper submission.

### Added

#### Core algorithm
- **DR-PPO agent** (`src/robin_fpga/agent.py`) — encoder + policy + value + slack
  regression + conformal sign-off, with CVaR-shaped advantage estimator.
- **GAT + MLP encoder** (`src/robin_fpga/encoder.py`) — two-layer graph attention
  (H=4 heads each) producing a 64-dim graph embedding, concatenated with a 32-dim
  tabular feature vector and projected through a three-layer GELU MLP to a
  128-dim latent state `z_t`.
- **CVaR module** (`src/robin_fpga/cvar.py`) — empirical VaR, CVaR, CVaR-shaped
  advantage estimator, Tamar et al. (2015) unbiased gradient estimator,
  beta-sensitivity diagnostics.
- **Split-conformal predictor** (`src/robin_fpga/conformal.py`) — calibrated
  envelope `C_{1-alpha}` over post-route WNS with deterministic SHA-256 audit
  hash and the accept/reject sign-off rule.
- **Categorical policy** (`src/robin_fpga/policy.py`) over 192 directive bundles.
- **Value and slack regression heads** (`src/robin_fpga/value.py`) for PPO
  baseline and conformal calibration.

#### Toolchain integration
- **Vivado environment wrapper** (`flows/vivado/`) — `synth.tcl`,
  `place_route.tcl`, `reports.tcl`, parametrised by directive-bundle deltas.
- **Quartus environment wrapper** (`flows/quartus/`) — `synthesis.tcl`,
  `fit.tcl`, `sta.tcl` covering Analysis & Synthesis, Fitter, and STA stages.
- **Device-agnostic feature normalizer** common to both flows (Figure 5).
- Parallel seed/corner fan-out via `concurrent.futures.ThreadPoolExecutor`.

#### Evaluation and reproducibility
- **Evaluator** (`src/robin_fpga/evaluator.py`) computing closure rate,
  sigma(WNS), CVaR_beta, empirical coverage, and Pareto frontier.
- **Calibrated simulator** (`src/robin_fpga/simulator.py`) generating all 13
  paper figure CSV files for reproducers without tool access.
- **Figure regeneration scripts** (`scripts/generate_figures.py`).
- **14-design benchmark catalogue** (`data/benchmarks/manifest.json`) spanning
  six workload classes (DSP, AI, Graph, Control, Sort, Crypto).

#### Tooling
- Comprehensive test suite (`tests/`) with >85% line coverage.
- CI via GitHub Actions: ruff + black + mypy + pytest + coverage upload.
- Documentation site (`docs/`) with architecture spec, usage guide,
  installation notes, reproduction protocol, and troubleshooting FAQ.
- Pre-commit hooks for ruff, black, and mypy.

### Documentation
- `README.md` with badges, quickstart, architecture diagram, key results table,
  full repository layout, citation, and contribution guide.
- Five end-to-end Jupyter notebooks under `notebooks/`.
- API reference auto-generated from docstrings.

### Known limitations
- Real toolchain integration tested with Vivado 2024.2 and Quartus Prime Pro 24.1
  only; older minor versions may fail parsing.
- The 4,900-run cluster sweep is still in progress; values in `data/results/`
  are calibrated simulator output. The simulator preserves pilot-run statistics
  (sigma per seed, residual distribution shape, CVaR concentration).

[Unreleased]: https://github.com/saher-elsayed/robin-fpga/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saher-elsayed/robin-fpga/releases/tag/v0.1.0
