# Paper

This directory contains the LaTeX source and the pre-built PDF of the ROBIN-FPGA paper submitted to IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems (TCAD).

## Contents

| File              | Description                                         |
|:------------------|:----------------------------------------------------|
| `robin-fpga.tex`  | Self-contained LaTeX source (all data inlined)       |
| `robin-fpga.pdf`  | Pre-built PDF (14 pages)                             |
| `BUILD.md`        | Instructions for building the paper from source      |
| `README.md`       | This file                                            |

## Quick view

The pre-built PDF in this directory is the latest revision. To read it directly:

```bash
xdg-open robin-fpga.pdf       # Linux
open robin-fpga.pdf           # macOS
```

## Citation

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

The full BibTeX entry, including software citation, is in [`../CITATION.bib`](../CITATION.bib).

## Figures

All 18 figures in the paper are TikZ / pgfplots, generated at compile time. The numerical data for the data-driven figures (Fig. 7–18) lives in [`../data/results/`](../data/results/) and is loaded inline in the `.tex` source. To regenerate the data from the calibrated simulator:

```bash
cd ..
make data        # writes data/results/*.csv
make paper       # rebuilds the PDF
```

## Reproducing the experiments

See [`../docs/reproduction.md`](../docs/reproduction.md).

## Source files

The single `robin-fpga.tex` file contains everything needed to build the paper:

- IEEEtran journal class (transmag option)
- All TikZ macros (FPGA fabric, timing graph, neural network, reward histogram, conformal envelope, FPGA stack)
- All 18 figures
- All data tables inlined (no external `.dat` files needed)
- Full bibliography (`thebibliography` environment, no external `.bib` needed)

This makes the source upload to Overleaf or a journal submission system frictionless.
