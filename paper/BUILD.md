# Building the Paper

## Requirements

A modern TeX Live distribution (2023 or newer):

### Ubuntu / Debian

```bash
sudo apt install texlive-full
```

`texlive-full` is large but covers everything used here. For a slimmer install:

```bash
sudo apt install texlive-latex-recommended texlive-fonts-recommended \
                 texlive-latex-extra texlive-fonts-extra texlive-science \
                 texlive-pictures texlive-pstricks texlive-pgf
```

### macOS

```bash
brew install --cask mactex
```

or BasicTeX (smaller, then `tlmgr install` the extras):

```bash
brew install --cask basictex
sudo tlmgr update --self
sudo tlmgr install ieeetran pgfplots tikz-3dplot collection-fontsrecommended
```

### Windows

Install [MikTeX](https://miktex.org/) or [TeX Live](https://www.tug.org/texlive/).

## Building

The paper is self-contained — all data, figures, and references are inlined. Two passes of `pdflatex` are sufficient (no `bibtex` needed because the bibliography uses the `thebibliography` environment).

```bash
cd paper/
pdflatex -interaction=nonstopmode robin-fpga.tex
pdflatex -interaction=nonstopmode robin-fpga.tex
```

Or use the project Makefile:

```bash
cd ..
make paper
```

Expected wall-clock time on a modern laptop: **~15 seconds**.

## Output

* `robin-fpga.pdf` — the camera-ready PDF (14 pages, ~600 KB).
* `robin-fpga.aux`, `.log`, `.out`, `.toc` — intermediate files (cleaned by `make clean`).

## Style class

The paper uses the IEEE Transactions journal class:

```latex
\documentclass[journal, twocolumn, 10pt, a4paper]{IEEEtran}
```

If you need a different paper variant (conference, technote, etc.), edit the first line of `robin-fpga.tex`.

## Figures regeneration

The data-driven figures (Fig. 7–18) read from CSV tables that are **inlined** in the source. If you regenerate the simulator data (`make data`), you also need to rebuild the source — the inline data is overwritten automatically by `scripts/inline_data.py` (called from `make paper`).

For a fully reproducible build:

```bash
make clean
make data
make paper
```

## Troubleshooting

### `pdflatex: command not found`

Install TeX Live (see above).

### `! LaTeX Error: File 'pgfplots.sty' not found`

Install `texlive-pictures` (Ubuntu) or `tlmgr install pgfplots` (BasicTeX).

### `! Package pgfplots Error: Sorry, support for pgfplots in TeX Live versions below 2018 is incomplete`

Update your TeX Live distribution to 2023 or newer.

### The paper compiles but figures look wrong / overlap

You're probably running a much older TikZ. The figures rely on `arrows.meta`, `calc`, `shadows`, `decorations.pathreplacing`, all available in TikZ 3.x. Update your TeX Live distribution.

### "Underfull \hbox" warnings

These are formatting warnings, not errors. The paper still compiles correctly. Most are at the column-break boundaries and are not visible in the PDF.

## Submission

For IEEE journal submission:

1. Single `.tex` file (already self-contained).
2. PDF as built by the steps above.
3. No supplementary `.bib`, `.bst`, `.dat`, or external image files needed.

The IEEE submission system (ScholarOne) accepts this packaging directly; no additional zipping or asset bundling is required.
