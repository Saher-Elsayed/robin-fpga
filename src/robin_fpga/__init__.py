"""ROBIN-FPGA: Distributionally-Robust RL with Conformal Sign-off for FPGA Timing Closure.

Public API
==========
Agent           — DR-PPO agent with GAT encoder
Environment     — FPGA toolchain wrapper (Vivado / Quartus)
ConformalSignoff — split-conformal predictor + sign-off rule
Trainer         — full training loop with CVaR-shaped advantage
Evaluator       — evaluation with calibrated envelopes
Simulator       — synthetic data generator (calibrated to pilot statistics)

Example
-------
>>> from robin_fpga import Agent, Environment, ConformalSignoff
>>> agent = Agent.from_checkpoint("runs/best.pt")
>>> env = Environment(rtl_path="design.v", device="xcve2302-sfva784-2MP-e-S")
>>> result = agent.close(env, episodes=50)
>>> signoff = ConformalSignoff.from_checkpoint("runs/best.pt", alpha=0.05)
>>> decision = signoff.evaluate(result)
"""

from robin_fpga.__version__ import __version__
from robin_fpga.agent import Agent
from robin_fpga.conformal import ConformalSignoff, SignoffDecision
from robin_fpga.cvar import cvar, cvar_advantage
from robin_fpga.encoder import Encoder
from robin_fpga.environment import Environment, ToolReport
from robin_fpga.evaluator import Evaluator
from robin_fpga.policy import Policy
from robin_fpga.simulator import Simulator
from robin_fpga.trainer import Trainer
from robin_fpga.value import Value

__all__ = [
    "__version__",
    "Agent",
    "ConformalSignoff",
    "SignoffDecision",
    "Encoder",
    "Environment",
    "Evaluator",
    "Policy",
    "Simulator",
    "ToolReport",
    "Trainer",
    "Value",
    "cvar",
    "cvar_advantage",
]
