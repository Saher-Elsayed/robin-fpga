# Troubleshooting

Common issues and fixes.

## Installation

### `ImportError: cannot import name 'torch'`

PyTorch was not installed alongside `robin-fpga`. Install:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu     # CPU-only
pip install torch --index-url https://download.pytorch.org/whl/cu121   # CUDA 12.1
```

### `vivado: command not found`

Source the Vivado setup script:

```bash
source /tools/Xilinx/Vivado/2024.2/settings64.sh
```

Or set explicitly:

```bash
export PATH="/tools/Xilinx/Vivado/2024.2/bin:$PATH"
```

### `quartus_sh: command not found`

```bash
source /opt/intelFPGA_pro/24.1/quartus/adm/qenv.sh
```

### License server unreachable

Test license connectivity:

```bash
# Vivado
lmstat -a -c $XILINXD_LICENSE_FILE

# Quartus
alm_lmstat -a -c $LM_LICENSE_FILE
```

## Training

### `NotImplementedError: Rollout collection requires an active Environment`

The `Trainer.train()` skeleton requires real toolchain rollouts. For simulator-driven training (no real Vivado/Quartus), use:

```bash
python scripts/run_simulator.py --output data/results/
```

A full simulator-driven `Trainer` will land in v0.2.

### Training crashes with `CUDA out of memory`

Reduce batch size:

```bash
robin-fpga train --config configs/versal.yaml --override training.batch_size=16
```

Or train on CPU:

```bash
robin-fpga train --device cpu ...
```

### Loss explodes / NaN gradients

- Check that your `clk_period_ns` in the reward config matches the design's actual target period.
- Lower the learning rate (`--override training.learning_rate=1e-4`).
- Verify `--override reward.kappa_fail=10.0` — if too large, a single route failure can dominate.

### Policy collapses to one action

Increase entropy regularisation:

```bash
--override training.entropy_coef=0.05
```

## Evaluation

### `RuntimeError: conformal predictor has not been calibrated yet`

Run the trainer for at least `calibration_interval` episodes (default 100) so the conformal predictor accumulates samples. Or skip the sign-off and use the raw policy:

```python
out = agent.act(...)
print(out["action"])   # no sign-off needed
```

### Empirical coverage well below target

This indicates a distribution shift between the calibration set and the test set. Common causes:

1. Tool minor-version drift (Section IX-D in the paper). Solution: recalibrate with samples from the current tool version.
2. PVT corner extrapolation: calibration done on `TT_25`, evaluation on `SS_125`. Solution: include extreme corners in the calibration set.
3. Cross-family transfer without fine-tuning. Solution: run 200 fine-tuning episodes (Section VII-D).

## Reproduction

### Figures look slightly different from paper

The simulator uses a fixed seed (42); if you changed it, results will differ within the noise band. To match the paper exactly:

```bash
python scripts/run_simulator.py --seed 42 --output data/results/
```

### `pdflatex` errors

Make sure you have a recent TeX Live distribution (>= 2023). Required packages: `pgfplots`, `tikz`, `IEEEtran`, `algorithmicx`, `algpseudocode`, `booktabs`, `siunitx`.

On Ubuntu:

```bash
sudo apt-get install texlive-full
```

## Tcl flows

### `synth.tcl` exits with `ERROR: --rtl and --part are required`

The Tcl script needs both flags. Common mistake: passing them via Python's `subprocess` without quoting paths with spaces. Use absolute paths and avoid spaces.

### Quartus fitter takes forever

Increase parallelism in the QSF action:

```
set_global_assignment -name NUM_PARALLEL_PROCESSORS 8
```

But beware: more parallelism may exhaust license seats on shared servers.

## Reporting Bugs

If none of the above helps, please [open an issue](https://github.com/saher-elsayed/robin-fpga/issues) using the [bug report template](https://github.com/saher-elsayed/robin-fpga/issues/new?template=bug_report.md).

Include:
- Output of `pip list` or `conda list`.
- Tool versions: `vivado -version`, `quartus_sh --version`.
- The full traceback.
- A minimal reproducer.
