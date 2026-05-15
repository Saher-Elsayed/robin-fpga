# Data Directory

This directory contains all data shipped with ROBIN-FPGA, organised as:

```
data/
├── benchmarks/                ← 14-design benchmark catalogue
│   ├── manifest.json          ← machine-readable index
│   └── <design>/              ← per-design RTL + constraints (not yet populated in this release)
│       ├── design.v
│       └── constraints.{xdc,sdc}
└── results/                   ← per-figure CSV data (regeneratable)
    ├── closure_rates.csv      ← Fig 7: heatmap (designs × baselines)
    ├── convergence.csv        ← Fig 8: training curves with CI bands
    ├── sigma_wns.csv          ← Fig 9: inter-seed sigma comparison
    ├── transfer.csv           ← Fig 10: cross-family fine-tuning
    ├── coverage.csv           ← Fig 11: conformal coverage diagnostic
    ├── pareto.csv             ← Fig 12: latency / power Pareto
    ├── per_design.csv         ← Fig 13: 4 designs × convergence
    ├── class_breakdown.csv    ← Fig 14: workload class breakdown
    ├── corner_wns.csv         ← Fig 15: PVT corner sensitivity
    ├── ablation.csv           ← Fig 16: component ablation
    ├── stress.csv             ← Fig 17: stress matrix
    ├── hack_clip.csv          ← Fig 18: reward-hacking trajectory (with WNS clip)
    └── hack_noclip.csv        ← Fig 18: reward-hacking trajectory (without clip)
```

## Benchmark catalogue (`benchmarks/manifest.json`)

The catalogue indexes 14 designs across six workload classes:

| Class    | Designs                                                         | Split            |
|----------|-----------------------------------------------------------------|------------------|
| DSP      | FFT-1024, FIR-256, BeamForm-8, CORDIC                            | train            |
| AI       | GEMM-systolic, MobileNet-V2                                      | train            |
| AI       | Attn-head                                                        | validation       |
| Graph    | BFS, PageRank                                                    | train            |
| Control  | PCIe-CSR, NoC-arbiter, Crossbar                                  | train            |
| Sort     | Bitonic-1024                                                     | train            |
| Crypto   | AES-128                                                          | validation       |
| Crypto   | SHA-3, NTT                                                       | held-out         |

Each entry includes target clock period, expected LUT count, license, and notes. RTL sources are not bundled in this release; users supply their own at the indicated `rtl_path` and `constraints_path` locations. A future release will ship permissively-licensed reference RTL.

## Result CSVs (`results/`)

All CSV files are regeneratable from the calibrated simulator:

```bash
python scripts/run_simulator.py --output data/results/ --seed 42
```

The CSVs are also versioned in this repo so reviewers can rebuild figures without a Python runtime.

### Schema of each CSV

| File                 | Columns                                                                 |
|----------------------|--------------------------------------------------------------------------|
| `closure_rates.csv`  | design, baseline, closure_rate                                           |
| `convergence.csv`    | episode, robin_mean, robin_p10, robin_p90, drills_mean, drills_p10, ... |
| `sigma_wns.csv`      | design, default, explore, DRiLLS, ROBIN-FPGA                             |
| `transfer.csv`       | episode, pretrained_AMD_to_Intel, from_scratch_Intel                     |
| `coverage.csv`       | alpha, target, exch_coverage, drift_coverage                             |
| `pareto.csv`         | method, latency_ns, power_W                                              |
| `per_design.csv`     | episode, GEMM, FFT, BFS, SHA-3                                           |
| `class_breakdown.csv`| class, Defaults, DRiLLS, ROBIN-FPGA                                       |
| `corner_wns.csv`     | corner, ROBIN_mean, ROBIN_std, DRiLLS_mean, DRiLLS_std                   |
| `ablation.csv`       | config, closure_rate_pp                                                  |
| `stress.csv`         | stress, closure_loss_pp, coverage_loss_pp, sigma_gain_pct                |
| `hack_clip.csv`      | episode, reward, pblock_size_pct                                         |
| `hack_noclip.csv`    | episode, reward, pblock_size_pct                                         |

## Calibration policy

The simulator is calibrated to pilot statistics observed on GEMM-systolic and NoC-arbiter pilot runs (preserved in `tests/fixtures/pilot_statistics.json` for regression tests). When the 4,900-run cluster sweep finishes, the corresponding measured CSVs will replace the simulator output bit-for-bit; the simulator is a stand-in for fast iteration only.
