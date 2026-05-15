# Benchmarks

ROBIN-FPGA ships a 14-design benchmark suite spanning six workload classes and two FPGA families. The catalogue is machine-readable at [`data/benchmarks/manifest.json`](../data/benchmarks/manifest.json).

## Design suite

| Class    | Design          | LUTs (est) | Period (ns) | Split      | License        |
|:---------|:----------------|-----------:|------------:|:-----------|:---------------|
| DSP      | FFT-1024        |       35K  | 5.0         | train      | BSD-3-Clause   |
| DSP      | FIR-256         |       24K  | 4.0         | train      | BSD-3-Clause   |
| DSP      | BeamForm-8      |       42K  | 5.0         | train      | Apache-2.0     |
| DSP      | CORDIC          |       18K  | 3.5         | train      | MIT            |
| AI       | GEMM-systolic   |      180K  | 5.0         | train      | Apache-2.0     |
| AI       | MobileNet-V2    |      380K  | 6.0         | train      | Apache-2.0     |
| AI       | Attn-head       |      220K  | 5.5         | validation | MIT            |
| Graph    | BFS             |       55K  | 4.5         | train      | BSD-3-Clause   |
| Graph    | PageRank        |       70K  | 4.5         | train      | BSD-3-Clause   |
| Control  | PCIe-CSR        |       28K  | 4.0         | train      | MIT            |
| Control  | NoC-arbiter     |       45K  | 3.5         | train      | Apache-2.0     |
| Control  | Crossbar        |       55K  | 4.5         | train      | MIT            |
| Sort     | Bitonic-1024    |       38K  | 4.5         | train      | BSD-3-Clause   |
| Crypto   | AES-128         |       32K  | 4.0         | validation | Apache-2.0     |
| Crypto   | SHA-3           |       88K  | 5.0         | held-out   | MIT            |
| Crypto   | NTT             |       60K  | 5.0         | held-out   | MIT            |

Note: the table lists 16 entries (10 train + 2 validation + 2 in-family test + 2 held-out cross-family). Only 14 are "active" at any given time; the suite supports either the in-family or cross-family protocol.

## Splits

- **Train (10 designs)**: used for policy training. Includes representatives from every workload class.
- **Validation (2)**: monitored during training for early-stop and hyperparameter selection.
- **In-family test (8)**: held out from training, same device family as training (e.g., AMD Versal AI Edge). Used to compute in-family closure rate (Fig. 7 in the paper).
- **Cross-family held-out (2)**: same designs, different device family (e.g., Intel Agilex 7). Used for cross-family transfer experiments (Table II).

## Metrics

| Metric | Description |
|--------|-------------|
| Closure rate | % of $K' = 10$ held-out seeds achieving WNS $\geq 0$ |
| $\sigma$(WNS) | inter-seed standard deviation of post-route WNS |
| Mean WNS | arithmetic mean WNS across seeds (ns) |
| CVaR$_\beta$ WNS | conditional value-at-risk at $\beta = 0.20$ |
| Empirical coverage | fraction of held-out runs whose WNS falls inside $\mathcal{C}_{1-\alpha}$ |
| Pareto frontier | non-dominated points on (latency, dynamic power) |

All metrics reported with 95% bootstrap confidence intervals over 1000 resamples; pairwise comparisons use Wilcoxon signed-rank with Bonferroni correction across baselines.

## Baselines

| Code | Description |
|------|-------------|
| **B1** | Vivado/Quartus defaults (no DSE) |
| **B2** | `Performance_Explore` strategy (Vivado) / `High Effort` (Quartus) |
| **B3** | Random search over directive bundles ($K = 200$ samples) |
| **B4** | TuRBO trust-region Bayesian optimisation |
| **B5** | DRiLLS-style DQN re-implemented for FPGA directive selection |
| **B6** | ROBIN-FPGA (this work) |

See [`src/robin_fpga/baselines/`](../src/robin_fpga/baselines/) (future release) for runnable implementations.

## Adding your own design

1. Drop your RTL/HLS into `data/benchmarks/<your_design>/`.
2. Add `constraints.xdc` (Vivado) or `constraints.sdc` (Quartus).
3. Append an entry to `data/benchmarks/manifest.json`:

```json
{
  "name":             "MyDesign",
  "workload_class":   "DSP",
  "rtl_path":         "my_design/design.v",
  "constraints_path": "my_design/constraints.xdc",
  "target_clock_ns":  5.0,
  "expected_luts":    50000,
  "split":            "validation",
  "license":          "MIT",
  "notes":            "what your design does"
}
```

4. Re-run the simulator calibration (`scripts/run_simulator.py`).
