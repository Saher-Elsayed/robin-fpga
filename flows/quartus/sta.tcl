# =====================================================================
# ROBIN-FPGA: Quartus Prime Pro Timing Analyzer (STA)
# Extracts post-fit timing into the canonical normalized schema.
# Invoked as:
#   quartus_sh -t flows/quartus/sta.tcl \
#              --proj runs/pnr/robin_design --out runs/sta/
# =====================================================================

package require ::quartus::project
package require ::quartus::flow
package require ::quartus::sta

# ---- parse args ----
set proj_path  ""
set out_dir    "./sta_out"
set corner     "TT_25"

for {set i 0} {$i < [llength $argv]} {incr i} {
    switch -exact -- [lindex $argv $i] {
        "--proj"   { incr i; set proj_path [lindex $argv $i] }
        "--out"    { incr i; set out_dir [lindex $argv $i] }
        "--corner" { incr i; set corner [lindex $argv $i] }
    }
}

if {$proj_path eq ""} {
    post_message -type error "--proj required"
    exit 1
}

file mkdir $out_dir
project_open $proj_path

# ---- run STA ----
create_timing_netlist
read_sdc
update_timing_netlist

# ---- extract worst slack across all setup paths ----
set setup_paths [get_timing_paths -setup -npaths 100 -nworst 100]
set wns 1e9
foreach p $setup_paths {
    set s [get_path_info $p -slack]
    if {$s < $wns} { set wns $s }
}

set hold_paths [get_timing_paths -hold -npaths 100 -nworst 100]
set hold_slack 1e9
foreach p $hold_paths {
    set s [get_path_info $p -slack]
    if {$s < $hold_slack} { set hold_slack $s }
}

set tns [get_clock_domain_info -tns]

# ---- emit JSON ----
set f [open $out_dir/report.json w]
puts $f "{"
puts $f "  \"stage\":         \"post_sta\","
puts $f "  \"corner\":        \"$corner\","
puts $f "  \"wns\":           $wns,"
puts $f "  \"hold_slack\":    $hold_slack,"
puts $f "  \"tns\":           $tns"
puts $f "}"
close $f

delete_timing_netlist
project_close
post_message "INFO: STA done -> $out_dir/report.json"
