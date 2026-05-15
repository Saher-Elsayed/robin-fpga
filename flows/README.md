# Vendor Tcl Flows

This directory contains the Tcl scripts that ROBIN-FPGA invokes to drive the AMD Vivado and Intel Quartus Prime Pro toolchains.

## Vivado (`vivado/`)

| File | Purpose |
|------|---------|
| `synth.tcl`       | Initial synthesis: `synth_design` + `opt_design`, emits the post-synthesis checkpoint and JSON summary. |
| `place_route.tcl` | Place-and-route: `place_design` + `phys_opt_design` + `route_design`, parametrised by seed, corner, and the policy's action XDC. |
| `reports.tcl`     | Standalone report extractor — converts vendor reports into the canonical normalized JSON schema. |
| `strategies.xdc`  | Library of XDC delta presets that the policy composes into directive bundles. |

Tested on Vivado 2024.2 (Versal AI Edge VE2302). Earlier versions may require adjusting the `phys_opt_design` directive names.

## Quartus (`quartus/`)

| File | Purpose |
|------|---------|
| `synthesis.tcl`   | Analysis & Synthesis (`quartus_map` equivalent) with QSF assignments. |
| `fit.tcl`         | Fitter (place-and-route + HyperFlex retiming) with action-deltas applied via QSF. |
| `sta.tcl`         | Standalone timing analyzer (`quartus_sta`) that produces the canonical JSON report. |
| `strategies.qsf`  | Library of QSF delta presets. |

Tested on Quartus Prime Pro 24.1 (Agilex 7 AGI 027). HyperFlex retiming requires Agilex or Stratix 10 silicon.

## Canonical normalized report schema

Both flows emit `report.json` files with the same keys (Figure 5 of the paper):

```json
{
  "wns":            0.18,        // Worst Negative Slack (ns)
  "tns":           -2.34,        // Total Negative Slack (ns)
  "hold_slack":     0.05,        // Worst hold slack (ns)
  "period_ns":      5.0,         // Target clock period (ns)
  "seed":           1,           // P&R seed
  "corner":         "SS_125C",   // PVT corner
  "route_failed":   false,
  "utilization":    {            // Per-resource utilisation (% of available)
    "LUT":  62.3,
    "FF":   45.7,
    "BRAM": 71.0,
    "DSP":  34.2,
    "URAM":  8.5
  },
  "congestion_pct":  [12.0, 18.5, 27.3, 41.6, 58.2],  // routing-cong. percentiles
  "power_dynamic":   3.85,
  "power_static":    0.41,
  "latency_ns":      4.82
}
```

The Python wrapper (`robin_fpga.environment.Environment._parse_report`) consumes this schema and never depends on vendor-specific report formats.

## Adding a new vendor

To add Lattice / Achronix / Microchip support:

1. Create `flows/<vendor>/` with three scripts following the same naming pattern: `synthesis.tcl`, `place_route.tcl` (or vendor equivalent), and a standalone STA parser.
2. Each must emit `report.json` in the canonical schema above.
3. Register the vendor in `robin_fpga.environment.Environment._build_command()`.
4. Add a YAML config under `configs/<vendor>.yaml`.
5. Add an integration test in `tests/baselines/` and ensure CI passes.
