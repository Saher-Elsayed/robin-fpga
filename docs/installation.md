# Installation

## System Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python    | >= 3.10 | 3.11 and 3.12 also tested |
| OS        | Linux (Ubuntu 22.04 LTS recommended) | macOS supported for development; tool integration is Linux-only |
| RAM       | 32 GB minimum, 256 GB recommended for cluster sweeps | |
| GPU       | NVIDIA, CUDA 11.8 or 12.1 | optional for training; required for fast iteration |
| Vivado    | 2024.2 or newer | for AMD device targets |
| Quartus   | Prime Pro 24.1 or newer | for Intel device targets |

## Quick install (Python only)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verify:

```bash
python -c "import robin_fpga; print(robin_fpga.__version__)"
pytest tests/ -v
```

## Conda environment

```bash
conda env create -f environment.yml
conda activate robin-fpga
pip install -e .
```

## Vivado integration

1. Install Vivado 2024.2 following AMD's official guide.
2. Source the setup script: `source /tools/Xilinx/Vivado/2024.2/settings64.sh`.
3. Confirm: `which vivado` should show the Vivado binary.
4. Configure the license server: `export XILINXD_LICENSE_FILE=2100@your-license-server`.
5. Test: `vivado -mode batch -source flows/vivado/synth.tcl -tclargs --rtl test.v --part xcve2302-sfva784-2MP-e-S`.

## Quartus integration

1. Install Quartus Prime Pro 24.1.
2. Source the setup script: `source /opt/intelFPGA_pro/24.1/quartus/adm/qenv.sh`.
3. Confirm: `which quartus_sh`.
4. Configure the license server: `export LM_LICENSE_FILE=1800@your-license-server`.
5. Test: `quartus_sh -t flows/quartus/synthesis.tcl --rtl test.v --part AGIB027R29A1E2VR0`.

## GPU drivers (optional)

For CUDA training:

```bash
# Check current driver
nvidia-smi

# Install CUDA toolkit (Ubuntu)
sudo apt-get install -y nvidia-cuda-toolkit
```

Make sure the PyTorch wheel matches your CUDA version. The `environment.yml` pins `pytorch-cuda=12.1`; for older drivers use:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common installation issues.
