---
name: Bug report
about: Report a reproducible problem with ROBIN-FPGA
title: '[BUG] '
labels: bug
assignees: ''
---

## Description

A clear, concise description of the bug.

## To Reproduce

Minimal steps that reproduce the behaviour:

1. Run `robin-fpga ...`
2. With config `...`
3. See error / wrong output

A code snippet or CLI command goes a long way:

```python
from robin_fpga import Agent
# ...
```

## Expected behaviour

What you expected to happen.

## Actual behaviour

What actually happened. Include the full traceback if applicable:

```
<paste traceback here>
```

## Environment

Run `robin-fpga doctor --verbose` and paste the output. If not installed yet:

- **OS:** [e.g. Ubuntu 22.04]
- **Python version:** [e.g. 3.11.6]
- **PyTorch version:** [e.g. 2.1.2]
- **CUDA version:** [e.g. 12.1, or "CPU-only"]
- **ROBIN-FPGA version:** [e.g. 0.1.0]
- **Tool version (if relevant):** [e.g. Vivado 2024.2, Quartus Prime Pro 24.1]

## Additional context

Add any other context that may help diagnose:

- Configuration YAML
- Run directory layout
- Hardware specifics (cluster size, GPU model)
- Whether this worked in a previous version
