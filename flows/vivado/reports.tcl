# =====================================================================
# ROBIN-FPGA: Vivado reports parser
# Extracts vendor reports into the canonical normalized schema:
#   (slack, period, path_type, startpoint, endpoint, hold_slack,
#    util_dict, corner)
# Output written as JSON to <out>/report.json
# =====================================================================

# ---- parse args ----
set dcp        ""
set out_dir    "./reports_out"
set seed       1
set corner     "TT_25"

for {set i 0} {$i < [llength $argv]} {incr i} {
    switch -exact -- [lindex $argv $i] {
        "--dcp"    { incr i; set dcp [lindex $argv $i] }
        "--out"    { incr i; set out_dir [lindex $argv $i] }
        "--seed"   { incr i; set seed [lindex $argv $i] }
        "--corner" { incr i; set corner [lindex $argv $i] }
    }
}

if {$dcp eq ""} {
    puts "ERROR: --dcp required"
    exit 1
}

file mkdir $out_dir
open_checkpoint $dcp

# ---- timing ----
set setup_paths [get_timing_paths -max_paths 100 -setup]
set hold_paths  [get_timing_paths -max_paths 100 -hold]

set wns [get_property SLACK [lindex $setup_paths 0]]
set tns [get_property TNS_TOTAL_ENDPOINT_SLACK [current_design]]
set hold_slack [get_property SLACK [lindex $hold_paths 0]]
set period [get_property REQUIREMENT [lindex $setup_paths 0]]

# ---- utilization ----
report_utilization -hierarchical -file $out_dir/util.rpt
# Parse util.rpt with a regex for canonical fields
set util_lut 0.0
set util_ff  0.0
set util_bram 0.0
set util_dsp  0.0
set util_uram 0.0
set f [open $out_dir/util.rpt r]
while {[gets $f line] >= 0} {
    if {[regexp -- {CLB LUTs\s+\|.*\|\s+([0-9\.]+)\s+\|} $line _ pct]} { set util_lut  $pct }
    if {[regexp -- {CLB Registers\s+\|.*\|\s+([0-9\.]+)\s+\|} $line _ pct]} { set util_ff $pct }
    if {[regexp -- {Block RAM Tile\s+\|.*\|\s+([0-9\.]+)\s+\|} $line _ pct]} { set util_bram $pct }
    if {[regexp -- {DSPs\s+\|.*\|\s+([0-9\.]+)\s+\|} $line _ pct]} { set util_dsp $pct }
    if {[regexp -- {URAM\s+\|.*\|\s+([0-9\.]+)\s+\|} $line _ pct]} { set util_uram $pct }
}
close $f

# ---- power ----
report_power -file $out_dir/power.rpt
set power_dyn 0.0
set power_sta 0.0
set f [open $out_dir/power.rpt r]
while {[gets $f line] >= 0} {
    if {[regexp -- {Dynamic\s+\(W\)\s+\|\s+([0-9\.]+)} $line _ p]} { set power_dyn $p }
    if {[regexp -- {Device Static\s+\(W\)\s+\|\s+([0-9\.]+)} $line _ p]} { set power_sta $p }
}
close $f

# ---- route status ----
set route_fail [expr {[get_property ROUTE_STATUS [current_design]] ne "ROUTED"}]

# ---- emit canonical JSON ----
set f [open $out_dir/report.json w]
puts $f "{"
puts $f "  \"wns\":          $wns,"
puts $f "  \"tns\":          $tns,"
puts $f "  \"hold_slack\":   $hold_slack,"
puts $f "  \"period_ns\":    $period,"
puts $f "  \"seed\":         $seed,"
puts $f "  \"corner\":       \"$corner\","
puts $f "  \"route_failed\": [expr {$route_fail ? "true" : "false"}],"
puts $f "  \"utilization\": {"
puts $f "    \"LUT\": $util_lut,"
puts $f "    \"FF\":  $util_ff,"
puts $f "    \"BRAM\": $util_bram,"
puts $f "    \"DSP\": $util_dsp,"
puts $f "    \"URAM\": $util_uram"
puts $f "  },"
puts $f "  \"power_dynamic\": $power_dyn,"
puts $f "  \"power_static\":  $power_sta,"
puts $f "  \"latency_ns\":    [expr {$period - $wns}]"
puts $f "}"
close $f

puts "INFO: report.json written to $out_dir"
