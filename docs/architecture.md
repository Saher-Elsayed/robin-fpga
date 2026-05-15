# Architecture

This document specifies the technical details of every component in ROBIN-FPGA. For the high-level overview, see the [README](../README.md).

## Table of Contents

1. [State and observation](#state-and-observation)
2. [Action space](#action-space)
3. [Encoder](#encoder)
4. [Policy head](#policy-head)
5. [Value head](#value-head)
6. [Slack-regression head and conformal calibration](#slack-regression-head-and-conformal-calibration)
7. [Reward function](#reward-function)
8. [DR-PPO objective](#dr-ppo-objective)
9. [Training algorithm](#training-algorithm)
10. [Sign-off rule](#sign-off-rule)

## State and observation

At episode step $t$, the observation $s_t$ consists of:

- A **post-synthesis timing graph** $G_t = (V_t, E_t)$ where
  - $V_t$ contains every endpoint and intermediate net node, each with features:
    - `slack` (ns)
    - `capacitance` (fF)
    - `fanout`
    - `level` (logic depth from clock)
    - `cell_type_onehot` (12-dim categorical encoding of standard cells)
  - $E_t$ contains directional dependency edges with features:
    - `wirelength_est` (post-synth estimated wirelength, mm)
    - `net_fanout`

- A **tabular feature vector** $x_t \in \mathbb{R}^{32}$:
  - Per-resource utilisation percentages $\{U_{\text{LUT}}, U_{\text{FF}}, U_{\text{BRAM}}, U_{\text{DSP}}, U_{\text{URAM}}\}$
  - Routing-congestion percentiles (5 values: 50th, 75th, 90th, 95th, 99th)
  - Tool-version one-hot
  - Device-family embedding (4-dim learned)
  - Last action $a_{t-1}$ embedding (12-dim)
  - Episode step index (normalised)
  - Six reserved fields for future extensions

## Action space

The action space $\mathcal{A}$ is a Cartesian product pruned to 192 feasible combinations:

| Axis | Cardinality | Examples |
|------|------------:|----------|
| Strategy preset | 4 | `Default`, `Performance_Explore`, `Congestion_SpreadLogic`, `Aggressive` |
| Phys-opt directive | 3 | `off`, `default`, `aggressive` |
| Pblock variant | 4 | whole-die, quadrant, eighth, sixteenth |
| Retiming | 2 | off, on |
| Route effort | 2 | default, high |

Total feasible: 192 (some combinations are pruned, e.g. `Aggressive` strategy is incompatible with quadrant pblock).

## Encoder

The encoder $\phi: (G_t, x_t) \to z_t \in \mathbb{R}^{128}$ is a two-layer GAT followed by an MLP fusion (Fig. 3 of the paper):

1. **GAT layer 1**: $H = 4$ attention heads, per-head output dimension $d_1 = 32$. Output is concatenated to $\mathbb{R}^{128}$ per node.
2. **GAT layer 2**: $H = 4$ heads, $d_2 = 64$. Output is concatenated to $\mathbb{R}^{256}$ per node.
3. **Graph readout**: mean + max pool over nodes, then a linear projection to $h^G_t \in \mathbb{R}^{64}$.
4. **Tabular projection**: $x_t \in \mathbb{R}^{32}$ -> $\text{Linear} \to \text{GELU} \to \tilde{x}_t \in \mathbb{R}^{64}$.
5. **MLP fusion**: three-layer MLP $\mathbb{R}^{128} \to \mathbb{R}^{128} \to \mathbb{R}^{128} \to \mathbb{R}^{128}$ with GELU activations producing $z_t$.

Total encoder parameter count: $\approx$ 230 K parameters.

## Policy head

Categorical distribution over $|\mathcal{A}| = 192$ actions:

$$\pi_\theta(a|z) = \text{Softmax}\big(\text{MLP}_{\pi}(z)\big)$$

Two-layer MLP $\mathbb{R}^{128} \to \mathbb{R}^{128} \to \mathbb{R}^{192}$ with GELU activation. $\approx$ 41 K parameters.

## Value head

Scalar value $V_\phi(z)$ estimating the expected discounted return:

$$V_\phi(z) = \text{MLP}_V(z): \mathbb{R}^{128} \to \mathbb{R}$$

Three-layer MLP $128 \to 128 \to 64 \to 1$ with GELU. Trained with smooth-L1 (Huber) loss. $\approx$ 25 K parameters.

## Slack-regression head and conformal calibration

A separate slack-regression head $\widehat{\mathrm{WNS}}(z) = \text{MLP}_W(z)$ predicts post-route WNS in nanoseconds:

$$\widehat{\mathrm{WNS}}: \mathbb{R}^{128} \to \mathbb{R}$$

Two-layer MLP $128 \to 64 \to 1$ with GELU. Trained with Huber loss against observed post-route WNS. $\approx$ 9 K parameters.

A held-out calibration set $\mathcal{D}_{\mathrm{cal}} = \{(z_i, \mathrm{WNS}_i)\}_{i=1}^{n}$ of size $n = 50$ feeds the split-conformal procedure to produce the envelope quantile $q_{1-\alpha}$:

$$
q_{1-\alpha} = \mathrm{Quantile}_{\lceil (n+1)(1-\alpha) \rceil / n} \Big( \{ |\mathrm{WNS}_i - \widehat{\mathrm{WNS}}(z_i)| \} \Big)
$$

The envelope is

$$\mathcal{C}_{1-\alpha}(z) = \big[\widehat{\mathrm{WNS}}(z) - q_{1-\alpha},\ \widehat{\mathrm{WNS}}(z) + q_{1-\alpha}\big].$$

Under exchangeability of $\mathcal{D}_{\mathrm{cal}}$ and a fresh test point, the conformal procedure guarantees marginal coverage

$$\Pr[\mathrm{WNS} \in \mathcal{C}_{1-\alpha}(z)] \geq 1 - \alpha.$$

## Reward function

Equation (3) in the paper:

$$r = w_{\mathrm{WNS}} \cdot \mathrm{clip}\!\left(\frac{\mathrm{WNS}}{T_{\mathrm{clk}}}, -1, 1\right)
   + w_{\mathrm{TNS}} \cdot \left(-\mathrm{sat}\!\left(\frac{|\mathrm{TNS}|}{T_{\mathrm{clk}}}\right)\right)
   - \kappa \cdot \sum_{i\in\mathcal{R}} (U_i - U_{\max}^i)^+
   - \mathbb{1}[\text{route fail}] \cdot \kappa_{\text{fail}}$$

with defaults $(w_{\mathrm{WNS}}, w_{\mathrm{TNS}}, \kappa, \kappa_{\text{fail}}) = (1.0, 0.3, 5.0, 10.0)$. The WNS clip prevents the reward-hacking failure mode where the agent shrinks pblocks to artificially inflate slack (see paper Fig. 18).

## DR-PPO objective

The PPO clipped surrogate with CVaR-shaped advantage:

$$\mathcal{L}^{\text{CLIP}}(\theta) = \mathbb{E}_t\Big[\min\big(\rho_t \hat A^\beta_t,\ \mathrm{clip}(\rho_t, 1-\epsilon, 1+\epsilon)\, \hat A^\beta_t\big)\Big]$$

with

$$\hat A^\beta_t = \mathrm{CVaR}_\beta(\{R_{k,\theta}\}) - V_\phi(z_t)$$

and importance ratio $\rho_t = \pi_\theta(a_t|z_t) / \pi_{\theta_{\text{old}}}(a_t|z_t)$. The combined loss is

$$\mathcal{L} = -\mathcal{L}^{\text{CLIP}} + c_v \mathcal{L}^V - c_e \mathcal{H}[\pi_\theta] + c_s \mathcal{L}^{\text{slack}}$$

with $(c_v, c_e, c_s) = (0.5, 0.01, 0.5)$ and $\beta = 0.20$ by default. $\mathcal{L}^{\text{slack}}$ is a Huber regression loss on $\widehat{\mathrm{WNS}}$.

## Training algorithm

See Algorithm 1 in the paper. Briefly:

```
for t = 0 to T-1:
    sample a_t ~ π(·|z_t)
    Δ ← ConstraintGen(a_t)
    parallel for (k, θ) in K × |Θ|:
        R_{k,θ} ← ToolRun(Δ, seed=k, corner=θ)
    Â_t ← CVaR_β({R_{k,θ}}) - V_φ(z_t)
    z_{t+1} ← Encoder(post-route reports)
    append (z_t, a_t, R̂, slack_target) to D_traj
    if EarlyTerminate(R) then break
θ ← PPO_Update(D_traj) with CVaR-shaped advantage
q_{1-α} ← split-conformal quantile from D_cal
return (closed design, C_{1-α}, audit manifest)
```

## Sign-off rule

A design is accepted iff the lower endpoint of the envelope is non-negative:

$$\boxed{\text{accept}\quad \iff \quad \widehat{\mathrm{WNS}}(z_T) - q_{1-\alpha} \geq 0}$$

The audit manifest records the SHA-256 hash of the policy weights, the tool version, the seed list, the corner list, the calibration size, and the conformal quantile. Any re-run with identical $(\theta, \text{tool}, \text{seeds}, \Theta)$ produces a bit-exact closure.
