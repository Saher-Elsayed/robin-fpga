"""Unit tests for robin_fpga.environment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from robin_fpga.environment import (
    Environment,
    PVTCorner,
    ToolReport,
    returns_from_reports,
    _default_corners,
)


class TestPVTCorner:
    def test_slug_format(self):
        c = PVTCorner("SS", "nominal", 125)
        assert c.slug() == "SS_nominal_125"

    def test_slug_negative_temp(self):
        c = PVTCorner("FF", "nominal", -40)
        assert c.slug() == "FF_nominal_m40"


class TestDefaultCorners:
    def test_returns_three_corners(self):
        corners = _default_corners()
        assert len(corners) == 3
        assert {c.process for c in corners} == {"SS", "TT", "FF"}


class TestEnvironmentConstruction:
    def test_invalid_tool_raises(self, tmp_path: Path):
        rtl = tmp_path / "design.v"
        rtl.write_text("module top; endmodule")
        xdc = tmp_path / "constraints.xdc"
        xdc.write_text("")
        with pytest.raises(ValueError):
            Environment(rtl_path=rtl, device="test", constraints=xdc, tool="lattice")

    def test_default_seeds(self, tmp_path: Path):
        rtl = tmp_path / "design.v"
        rtl.write_text("module top; endmodule")
        xdc = tmp_path / "constraints.xdc"
        xdc.write_text("")
        env = Environment(rtl_path=rtl, device="x", constraints=xdc, tool="vivado",
                          workdir=tmp_path / "work")
        assert len(env.seeds) == 10
        assert env.seeds == list(range(1, 11))


class TestReturnsFromReports:
    def test_failed_run_returns_penalty(self):
        r = ToolReport(
            wns=0.0, tns=0.0, utilization={}, congestion_pct=[],
            power_dynamic=0.0, power_static=0.0, latency_ns=0.0,
            route_failed=True,
        )
        ret = returns_from_reports([r], kappa_fail=10.0)
        assert ret[0] == pytest.approx(-10.0)

    def test_positive_wns_yields_positive_return(self):
        r = ToolReport(
            wns=0.5, tns=0.0, utilization={"LUT": 50.0, "FF": 40.0},
            congestion_pct=[20.0], power_dynamic=1.0, power_static=0.1,
            latency_ns=4.5, route_failed=False,
        )
        ret = returns_from_reports([r], clk_period_ns=5.0)
        assert ret[0] > 0

    def test_negative_wns_yields_negative_return(self):
        r = ToolReport(
            wns=-0.5, tns=-2.0, utilization={"LUT": 50.0, "FF": 40.0},
            congestion_pct=[20.0], power_dynamic=1.0, power_static=0.1,
            latency_ns=5.5, route_failed=False,
        )
        ret = returns_from_reports([r], clk_period_ns=5.0)
        assert ret[0] < 0

    def test_util_overshoot_penalised(self):
        # design over the LUT budget
        r_ok = ToolReport(
            wns=0.5, tns=0.0,
            utilization={"LUT": 60.0, "FF": 50.0, "BRAM": 50.0, "DSP": 50.0, "URAM": 50.0},
            congestion_pct=[20.0], power_dynamic=1.0, power_static=0.1,
            latency_ns=4.5,
        )
        r_over = ToolReport(
            wns=0.5, tns=0.0,
            utilization={"LUT": 85.0, "FF": 50.0, "BRAM": 50.0, "DSP": 50.0, "URAM": 50.0},
            congestion_pct=[20.0], power_dynamic=1.0, power_static=0.1,
            latency_ns=4.5,
        )
        ret_ok = returns_from_reports([r_ok])
        ret_over = returns_from_reports([r_over])
        assert ret_over[0] < ret_ok[0]
