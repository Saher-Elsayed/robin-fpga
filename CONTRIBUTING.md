# Contributing to ROBIN-FPGA

Thanks for your interest in contributing! This document outlines how to get involved.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Reporting Issues](#reporting-issues)
- [Development Setup](#development-setup)
- [Submitting Changes](#submitting-changes)
- [Style Guide](#style-guide)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [Adding Benchmark Designs](#adding-benchmark-designs)
- [Adding Baselines](#adding-baselines)
- [Release Process](#release-process)

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Reporting Issues

When filing a bug report, please include:

1. A minimal reproducer (Python snippet or a CLI invocation).
2. Output of `pip list` (or `conda list`).
3. Tool versions if relevant (Vivado / Quartus / OS).
4. Expected vs actual behaviour.
5. Full traceback when applicable.

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) where possible.

For feature requests, the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) helps frame the discussion.

## Development Setup

```bash
git clone https://github.com/saher-elsayed/robin-fpga.git
cd robin-fpga
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
pre-commit install
```

Run the test suite to verify your setup:

```bash
make test
```

## Submitting Changes

1. Fork the repository and create a feature branch off `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes following the [style guide](#style-guide).
3. Add tests covering new behaviour. Existing tests must continue to pass.
4. Run `make lint type-check test` before pushing.
5. Open a pull request against `main`. Reference any related issues in the description.
6. The CI pipeline runs ruff, black, mypy, and pytest. PRs that do not pass CI cannot be merged.

For non-trivial changes, please open an issue first to discuss the design.

## Style Guide

- **Formatting:** `black` (line length 100).
- **Linting:** `ruff` with the project ruleset (see `pyproject.toml`).
- **Types:** annotate public APIs; `mypy` runs on `src/robin_fpga`.
- **Imports:** `ruff` handles import ordering (`isort` profile).
- **Docstrings:** NumPy style for public API; one-liners are fine for internal helpers.
- **Commits:** prefer imperative mood, one logical change per commit.

## Testing Requirements

- New modules require unit tests in `tests/test_<module>.py`.
- Maintain coverage at or above 85%.
- Integration tests (those touching real Vivado / Quartus) must be marked with `@pytest.mark.integration` and gated by environment variables.

## Documentation

User-facing changes must update `docs/`. API reference is auto-generated from docstrings, so make sure your public functions and classes are documented.

To build the docs locally:

```bash
make docs
make serve-docs   # open http://localhost:8000
```

## Adding Benchmark Designs

To add a new design to the catalogue:

1. Add the RTL/HLS sources under `data/benchmarks/<your_design>/`.
2. Add a constraint file (`.xdc` for Vivado, `.sdc` for Quartus).
3. Update `data/benchmarks/manifest.json` with a new entry.
4. Run `python scripts/run_simulator.py` to refresh simulator calibration.
5. Include a license attribution; only permissively-licensed designs are accepted.

## Adding Baselines

When introducing a new baseline method:

1. Add the implementation under `src/robin_fpga/baselines/<your_baseline>.py`.
2. Conform to the `Baseline` protocol (see `src/robin_fpga/baselines/protocol.py`).
3. Add a configuration preset under `configs/baselines/<your_baseline>.yaml`.
4. Add regression tests under `tests/baselines/`.
5. Update Table I in the paper if results materially change.

## Release Process

Releases follow [semantic versioning](https://semver.org/):

1. Bump version in `src/robin_fpga/__version__.py` and `pyproject.toml`.
2. Update `CHANGELOG.md` with all notable changes.
3. Tag the release: `git tag v0.X.Y && git push --tags`.
4. CI publishes to PyPI automatically via `.github/workflows/publish.yml`.

Thanks for contributing!
