# =====================================================================
# ROBIN-FPGA: Quartus Prime Pro fitter (place & route) flow
# Invoked as:
#   quartus_sh -t flows/quartus/fit.tcl \
#              --rtl design.v --part AGIB027R29A1E2VR0 \
#              --sdc design.sdc --action action.qsf \
#              --seed 1 --corner SS_125C --out runs/pnr/
# =====================================================================

package require ::quartus::project
package require ::quartus::flow

# ---- parse args ----
set rtl_files  ""
set part       ""
set sdc_file   ""
set action_qsf ""
set seed       1
set corner     "TT_25"
set out_dir    "./fit_out"
set proj_name  "robin_design"

for {set i 0} {$i < [llength $argv]} {incr i} {
    set arg [lindex $argv $i]
    switch -exact -- $arg {
        "--rtl"    { incr i; set rtl_files [lindex $argv $i] }
        "--part"   { incr i; set part [lindex $argv $i] }
        "--sdc"    { incr i; set sdc_file [lindex $argv $i] }
        "--action" { incr i; set action_qsf [lindex $argv $i] }
        "--seed"   { incr i; set seed [lindex $argv $i] }
        "--corner" { incr i; set corner [lindex $argv $i] }
        "--out"    { incr i; set out_dir [lindex $argv $i] }
    }
}

file mkdir $out_dir

# ---- open or create project ----
if {[file exists $out_dir/$proj_name.qpf]} {
    project_open $out_dir/$proj_name
} else {
    project_new $out_dir/$proj_name -overwrite
    set_global_assignment -name FAMILY "Agilex 7"
    set_global_assignment -name DEVICE $part
    foreach src [split $rtl_files ","] {
        if {[regexp {\.v$|\.sv$}     $src]} { set_global_assignment -name SYSTEMVERILOG_FILE $src }
        if {[regexp {\.vhd$|\.vhdl$} $src]} { set_global_assignment -name VHDL_FILE $src }
    }
    if {$sdc_file ne ""} { set_global_assignment -name SDC_FILE $sdc_file }
}

# ---- apply policy action deltas (additional QSF assignments) ----
if {$action_qsf ne "" && [file exists $action_qsf]} {
    set f [open $action_qsf r]
    while {[gets $f line] >= 0} {
        if {[string length [string trim $line]] > 0} {
            eval $line
        }
    }
    close $f
    post_message "INFO: applied action deltas from $action_qsf"
}

# ---- seed the fitter ----
set_global_assignment -name SEED $seed

# ---- enable HyperFlex retiming (Agilex/Stratix-10 only) ----
set_global_assignment -name OPTIMIZATION_MODE "HIGH PERFORMANCE EFFORT"
set_global_assignment -name HYPER_RETIMER_AGGRESSIVE_LOOP_OPTIMIZATIONS ON

# ---- run Analysis & Synthesis + Fitter (map + fit) ----
execute_module -tool map
execute_module -tool fit

# ---- emit JSON summary ----
load_package report
load_report
set wns 0.0
set tns 0.0
catch {
    set wns [get_timing_analysis_summary_panel_data -row 0 -panel_name "Slack" -col 1]
}
set route_fail false
if {[catch {execute_module -tool fit -dry_run} _]} { set route_fail true }
set f [open $out_dir/report.json w]
puts $f "{"
puts $f "  \"stage\":         \"post_fit\","
puts $f "  \"seed\":          $seed,"
puts $f "  \"corner\":        \"$corner\","
puts $f "  \"wns\":           $wns,"
puts $f "  \"tns\":           $tns,"
puts $f "  \"hold_slack\":    0.0,"
puts $f "  \"route_failed\":  $route_fail,"
puts $f "  \"utilization\":   {\"LUT\": 0.0, \"FF\": 0.0, \"BRAM\": 0.0, \"DSP\": 0.0, \"URAM\": 0.0},"
puts $f "  \"congestion_pct\": \[],"
puts $f "  \"power_dynamic\": 0.0,"
puts $f "  \"power_static\":  0.0,"
puts $f "  \"latency_ns\":    0.0"
puts $f "}"
close $f
unload_report

post_message "INFO: quartus fit done for seed=$seed corner=$corner"
project_close
