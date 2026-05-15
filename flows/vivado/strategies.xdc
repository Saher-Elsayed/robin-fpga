# =====================================================================
# ROBIN-FPGA: Vivado strategy bundle templates (XDC deltas)
#
# The 192-action policy emits one of these bundles per step. They are
# composed of orthogonal axes:
#   STRATEGY:  Default | Performance_Explore | Congestion_SpreadLogic |
#              Aggressive
#   PHYS_OPT:  off | default | aggressive
#   PBLOCK:    whole | quadrant | eighth | sixteenth
#   RETIME:    off | on
#   ROUTE:     default | high
#
# This file is sourced from place_route.tcl after read_xdc on the
# user constraints.
# =====================================================================

# ---- placeholder XDC delta — overwritten per-step by the policy ----
# The policy serialises its action via robin_fpga.environment._write_action_tcl
# into a fresh `action.xdc` file referenced via -tclargs --action ...

# Canonical strategy presets:
# set_property STRATEGY Performance_Explore  [get_runs synth_1]
# set_property STRATEGY Performance_ExtraTimingOpt [get_runs impl_1]
# set_property STRATEGY Congestion_SpreadLogic_high [get_runs impl_1]
# set_property STRATEGY Aggressive   [get_runs impl_1]

# Phys-opt flags:
# set_property phys_opt_design.is_enabled true [current_design]
# set_property phys_opt_design.directive ExploreWithAggressiveHoldFix [current_design]

# Retiming:
# set_property RETIMING true [current_design]

# Route effort:
# set_property route_design.directive Explore        [current_design]
# set_property route_design.directive ExploreWithRemap [current_design]
# set_property route_design.directive Aggressive    [current_design]

# Pblock variants — illustrative for a 4x4 device grid:
# create_pblock pblock_top
# resize_pblock pblock_top -add CLOCKREGION_X0Y0:CLOCKREGION_X3Y3
# add_cells_to_pblock pblock_top [get_cells -hier]

# ---- end ----
