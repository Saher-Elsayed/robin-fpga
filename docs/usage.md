# Usage

## CLI Reference

The `robin-fpga` CLI exposes three primary commands.

### `robin-fpga train`

Train a DR-PPO policy on a single design.

```bash
robin-fpga train \
  --config configs/versal.yaml \
  --design data/benchmarks/gemm_systolic/ \
  --episodes 1200 \
  --output runs/gemm_versal/
```

Key flags:

| Flag           | Default          | Description |
|----------------|------------------|-------------|
| `--config`     | required         | YAML config file |
| `--design`     | required         | benchmark design directory |
| `--episodes`   | from config      | override episode count |
| `--output`     | `./runs`         | output directory |
| `--device`     | auto             | cpu / cuda |
| `--override`   | (repeatable)     | `key.path=value` config overrides |

### `robin-fpga evaluate`

Evaluate a trained checkpoint with conformal sign-off.

```bash
robin-fpga evaluate \
  --checkpoint runs/best.pt \
  --design data/benchmarks/gemm_systolic/ \
  --seeds 10 \
  --alpha 0.05 \
  --output eval/
```

The exit code is 0 if the design is accepted by the sign-off rule, 1 otherwise.

### `robin-fpga simulate`

Regenerate paper figure data from the calibrated simulator (no toolchain required).

```bash
robin-fpga simulate --output data/results/ --seed 42
```

## Python API

### Load a checkpoint and run a sign-off

```python
from robin_fpga import Agent, Environment, ConformalSignoff

agent = Agent.from_checkpoint("runs/best.pt")

env = Environment(
    rtl_path="my_design.v",
    device="xcve2302-sfva784-2MP-e-S",
    constraints="my_design.xdc",
    tool="vivado",
    tool_version="2024.2",
)

# Run K seeds through the toolchain
obs = env.reset()
action_dict = {"STRATEGY": "Aggressive", "RETIME": 1}
reports, info = env.step(action_dict)

# Decide accept/reject
signoff = agent.signoff(*observation_tensors)
print(signoff[0].accepted, signoff[0].lower, signoff[0].upper)
```

### Train a fresh agent

```python
from robin_fpga import Agent, Trainer
from robin_fpga.trainer import TrainerConfig

agent = Agent()
trainer = Trainer(agent, env, TrainerConfig(episodes=500))
history = trainer.train()
```

### Evaluate against multiple baselines

```python
from robin_fpga import Evaluator

evaluator = Evaluator(agent, env)
report = evaluator.evaluate(num_seeds=10, beta=0.20)
print(f"Closure rate: {report.closure_rate:.1%}")
print(f"sigma(WNS):    {report.sigma_wns:.3f} ns")
print(f"Coverage:     {report.empirical_coverage:.3f}")
```

## Configuration

Configurations are YAML files in `configs/`. The `extends:` directive composes configs:

```yaml
# configs/my_experiment.yaml
extends: versal.yaml

training:
  episodes: 2000
  cvar_beta: 0.10    # tighter risk hedging
```

Override any field from the CLI:

```bash
robin-fpga train --config configs/versal.yaml \
                 --override training.cvar_beta=0.10 \
                 --override training.episodes=2000
```

## Logging

ROBIN-FPGA writes TensorBoard summaries to `runs/<id>/tb/`. Launch:

```bash
tensorboard --logdir runs/
```

Enable W&B by adding to your YAML:

```yaml
logging:
  wandb: true
  wandb_project: robin-fpga
```

## Reproducibility

Every accepted closure ships an audit manifest at `runs/<id>/audit.json`:

```json
{
  "design":         "gemm_systolic",
  "device":         "xcve2302-sfva784-2MP-e-S",
  "tool":           "vivado",
  "tool_version":   "2024.2",
  "seeds":          [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "corners":        ["SS_125", "TT_25", "FF_m40"],
  "weights_hash":   "3e4f...",
  "conformal_q":    0.142,
  "decision":       "accept",
  "wns_predicted":  0.18,
  "envelope":       [0.038, 0.322]
}
```

Hash collisions on the audit hash guarantee bit-exact reproduction of the closure within the same tool environment.
