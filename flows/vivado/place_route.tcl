# =====================================================================
# ROBIN-FPGA: Vivado place & route flow
# Invoked as:
#   vivado -mode batch -source flows/vivado/place_route.tcl \
#          -tclargs --dcp post_synth.dcp --action action.xdc \
#                   --seed 1 --corner SS_125C --out runs/pnr/
# =====================================================================

# ---- parse args ----
set dcp_file   ""
set action_xdc ""
set seed       1
set corner     "TT_25"
set out_dir    "./pnr_out"
set part       ""
set rtl        ""
set xdc        ""

for {set i 0} {$i < [llength $argv]} {incr i} {
    set arg [lindex $argv $i]
    switch -exact -- $arg {
        "--dcp"    { incr i; set dcp_file [lindex $argv $i] }
        "--action" { incr i; set action_xdc [lindex $argv $i] }
        "--seed"   { incr i; set seed [lindex $argv $i] }
        "--corner" { incr i; set corner [lindex $argv $i] }
        "--out"    { incr i; set out_dir [lindex $argv $i] }
        "--part"   { incr i; set part [lindex $argv $i] }
        "--rtl"    { incr i; set rtl [lindex $argv $i] }
        "--xdc"    { incr i; set xdc [lindex $argv $i] }
        default    { puts "WARN: unknown arg $arg" }
    }
}

file mkdir $out_dir

# ---- load checkpoint or re-run synth ----
if {$dcp_file ne "" && [file exists $dcp_file]} {
    open_checkpoint $dcp_file
} elseif {$rtl ne "" && $part ne ""} {
    puts "INFO: no DCP given, running synthesis first"
    source [file dirname [info script]]/synth.tcl \
        -tclargs --rtl $rtl --part $part --xdc $xdc --out $out_dir
    open_checkpoint $out_dir/post_synth.dcp
} else {
    puts "ERROR: provide --dcp or (--rtl + --part)"
    exit 1
}

# ---- apply the policy's action deltas ----
if {$action_xdc ne "" && [file exists $action_xdc]} {
    puts "INFO: applying action deltas from $action_xdc"
    read_xdc $action_xdc
}

# ---- seed the placer ----
set_param place.placerSeed $seed

# ---- place ----
place_design

# ---- phys_opt (timing-driven physical optimisation) ----
phys_opt_design -directive ExploreWithAggressiveHoldFix

# ---- route ----
route_design -directive ExploreWithRemap

# ---- post-route phys_opt ----
phys_opt_design -directive AggressiveExplore

# ---- reports ----
report_timing_summary    -file $out_dir/post_route_timing.rpt -warn_on_violation
report_utilization       -file $out_dir/post_route_util.rpt   -hierarchical
report_power             -file $out_dir/post_route_power.rpt
report_route_status      -file $out_dir/route_status.rpt
write_checkpoint -force  $out_dir/post_route.dcp

# ---- emit a JSON summary that the python wrapper parses ----
set wns         [get_property SLACK [get_timing_paths -max_paths 1 -setup]]
set tns         [get_property TNS_TOTAL_ENDPOINT_SLACK [current_design]]
set hold_slack  [get_property SLACK [get_timing_paths -max_paths 1 -hold]]
set route_fail  [expr {[get_property ROUTE_STATUS [current_design]] ne "ROUTED"}]

# utilisation
set util_lut    [get_property UTILIZATION [get_property -of [current_design] PROGRESS]]
# (canonical implementation reads from report_utilization rpt; placeholder shown)
set f [open $out_dir/report.json w]
puts $f "{"
puts $f "  \"stage\":         \"post_route\","
puts $f "  \"seed\":          $seed,"
puts $f "  \"corner\":        \"$corner\","
puts $f "  \"wns\":           $wns,"
puts $f "  \"tns\":           $tns,"
puts $f "  \"hold_slack\":    $hold_slack,"
puts $f "  \"route_failed\":  [expr {$route_fail ? "true" : "false"}],"
puts $f "  \"utilization\":   {\"LUT\": 0.0, \"FF\": 0.0, \"BRAM\": 0.0, \"DSP\": 0.0, \"URAM\": 0.0},"
puts $f "  \"congestion_pct\": \[],"
puts $f "  \"power_dynamic\": 0.0,"
puts $f "  \"power_static\":  0.0,"
puts $f "  \"latency_ns\":    0.0"
puts $f "}"
close $f

puts "INFO: P\\&R done for seed=$seed corner=$corner -> $out_dir/report.json"
