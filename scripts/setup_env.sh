#!/usr/bin/env bash
# =====================================================================
# ROBIN-FPGA: development environment bootstrap
# Sets up a virtualenv, installs dev dependencies, and runs sanity tests.
# Usage: bash scripts/setup_env.sh [venv_dir]
# =====================================================================
set -euo pipefail

VENV_DIR="${1:-.venv}"

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found in PATH"
  exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Detected Python $PYTHON_VERSION"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating venv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

echo "Installing robin-fpga with dev extras..."
pip install -e ".[dev,docs]"

echo "Installing pre-commit hooks..."
pre-commit install

echo
echo "Running sanity check..."
python -c "import robin_fpga; print(f'OK: robin_fpga {robin_fpga.__version__}')"

echo
echo "Running quick test suite..."
pytest tests/ -x -q --no-cov || echo "WARNING: some tests failed"

echo
echo "================================================================"
echo "Setup complete. To activate the environment:"
echo "    source $VENV_DIR/bin/activate"
echo "================================================================"
