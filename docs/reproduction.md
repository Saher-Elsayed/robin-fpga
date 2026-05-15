# Reproducing the Paper

This document describes the exact procedure to reproduce every figure and table in the IEEE TCAD submission.

## Quick reproduction (simulator)

Without a Vivado/Quartus installation, you can rebuild every figure in under 30 seconds:

```bash
make data        # ~5s — runs scripts/run_simulator.py
make figures     # ~15s — runs scripts/generate_figures.py
make paper       # ~10s — pdflatex twice
```

The simulator is calibrated to pilot statistics observed on GEMM-systolic and NoC-arbiter pilot runs. It preserves the qualitative effects predicted by ROBIN-FPGA's contributions: cross-baseline closure-rate ordering, sigma reduction under CVaR, coverage near target under exchangeability, drift-induced degradation, cross-family transfer cost reduction, and Pareto frontier dominance.

## Full reproduction (toolchain)

To reproduce with real Vivado and Quartus runs, you need:

* Vivado 2024.2 and 2024.2.1 (the latter is needed for the tool-version drift experiment in Section IX-D).
* Quartus Prime Pro 24.1 and 24.2.
* AMD Versal AI Edge VE2302 license entitlement.
* Intel Agilex 7 AGI 027 license entitlement.
* A compute cluster with ~ 256 GB RAM/node and at least 96 cores. The 4900-run sweep takes ~ 240 GPU-hours and ~ 80,000 CPU-hours.

### Step 1: configure cluster

Edit `configs/cluster.yaml` (not included; see [`scripts/benchmark.sh`](../scripts/benchmark.sh) for SLURM examples). The benchmark sweep is naively parallelisable across (design, seed, corner).

### Step 2: run the training sweep

```bash
bash scripts/benchmark.sh versal
bash scripts/benchmark.sh agilex
```

This produces a tree under `runs/<timestamp>_versal_sweep/<design>/` for each design. Each contains `best.pt`, `history.json`, and `audit.json`.

### Step 3: extract per-figure data

```bash
python scripts/extract_figure_data.py \
  --sweep runs/<timestamp>_versal_sweep \
  --output data/results_measured/
```

(`extract_figure_data.py` is part of the supplemental release; in this v0.1.0 the simulator output stands in.)

### Step 4: regenerate paper figures

The IEEE paper renders figures inline from `data/results_measured/*.csv` using pgfplots/TikZ. Drop in the measured CSVs:

```bash
cp data/results_measured/*.csv data/results/
make paper
```

The resulting PDF should be bit-for-bit identical to the camera-ready (modulo PDF metadata).

## Per-figure reproduction map

| Figure | Data file | Script | Paper section |
|:-------|:----------|:-------|:--------------|
| Fig 1 (cover, pipeline)             | (synthetic) | inline TikZ           | I             |
| Fig 2 (FPGA anatomy)                | (synthetic) | inline TikZ           | II            |
| Fig 3 (architecture)                | (synthetic) | inline TikZ           | V             |
| Fig 4 (DR-MDP loop)                 | (synthetic) | inline TikZ           | V             |
| Fig 5 (dual toolchain)              | (synthetic) | inline TikZ           | V             |
| Fig 6 (benchmark suite)             | manifest.json | inline TikZ         | VI            |
| Fig 7 (closure rate heatmap)        | closure_rates.csv  | generate_figures.py | VII-A      |
| Fig 8 (convergence)                 | convergence.csv    | generate_figures.py | VII-B      |
| Fig 9 (sigma WNS bars)              | sigma_wns.csv      | generate_figures.py | VII-C      |
| Fig 10 (cross-family transfer)      | transfer.csv       | generate_figures.py | VII-D      |
| Fig 11 (conformal coverage)         | coverage.csv       | generate_figures.py | VII-E      |
| Fig 12 (Pareto frontier)            | pareto.csv         | generate_figures.py | VII-F      |
| Fig 13 (per-design convergence)     | per_design.csv     | generate_figures.py | VII        |
| Fig 14 (class breakdown)            | class_breakdown.csv | generate_figures.py | VII        |
| Fig 15 (PVT corner sensitivity)     | corner_wns.csv     | generate_figures.py | VIII-A     |
| Fig 16 (ablation)                   | ablation.csv       | generate_figures.py | VIII-B     |
| Fig 17 (stress matrix)              | stress.csv         | generate_figures.py | VIII-D     |
| Fig 18 (reward hacking)             | hack_*.csv         | generate_figures.py | IX-A       |

## Random seeds

The full reproduction uses the following seeds:

- Training: `42`, `43`, `44` (3 training seeds per experiment for the convergence-band plots).
- P&R within an episode: `1..10` (the K=10 seeds per step).
- Held-out evaluation: `101..110` (disjoint from training).
- Bootstrap resampling: `0..999`.

All seeds are recorded in each `audit.json` for bit-exact reproduction.

## Tool versions

The exact tool versions used in the paper are:

- Vivado 2024.2 (build 4525713)
- Vivado 2024.2.1 (build 4660870) — drift experiment only
- Quartus Prime Pro 24.1 (build 187) — Intel sweeps
- Quartus Prime Pro 24.2 (build 121) — drift experiment only

Tool-version drift is detected by SHA-256 hashing the tool's `synth_design` deterministic logic-path signature. The audit manifest records the hash so reviewers can confirm version compatibility.

## Statistical methodology

All claims of improvement come with explicit statistical tests:

- **Closure rate**: Wilson 95% confidence interval; pairwise comparisons via Fisher's exact test with Bonferroni correction.
- **sigma(WNS)**: 1000-iteration bootstrap CI; F-test for variance equality across methods.
- **Coverage**: Clopper-Pearson 95% interval on the empirical proportion.
- **Convergence curves**: bootstrap 10/90 percentile bands over 10 training seeds.
- **Pareto dominance**: domination count and hypervolume ratio.

Significance threshold: $p < 0.05$ after correction.
