# =====================================================================
# ROBIN-FPGA: Quartus Prime Pro synthesis flow
# Invoked as:
#   quartus_sh -t flows/quartus/synthesis.tcl \
#              --rtl design.v --part AGIB027R29A1E2VR0 \
#              --sdc design.sdc --out runs/synth/
# =====================================================================

package require ::quartus::project
package require ::quartus::flow

# ---- parse args ----
set rtl_files  ""
set part       ""
set sdc_file   ""
set out_dir    "./synth_out"
set top_module "top"
set proj_name  "robin_design"

for {set i 0} {$i < [llength $argv]} {incr i} {
    set arg [lindex $argv $i]
    switch -exact -- $arg {
        "--rtl"  { incr i; set rtl_files [lindex $argv $i] }
        "--part" { incr i; set part [lindex $argv $i] }
        "--sdc"  { incr i; set sdc_file [lindex $argv $i] }
        "--out"  { incr i; set out_dir [lindex $argv $i] }
        "--top"  { incr i; set top_module [lindex $argv $i] }
    }
}

if {$rtl_files eq "" || $part eq ""} {
    post_message -type error "--rtl and --part are required"
    exit 1
}

file mkdir $out_dir

# ---- create project ----
project_new $out_dir/$proj_name -overwrite
set_global_assignment -name FAMILY "Agilex 7"
set_global_assignment -name DEVICE $part
set_global_assignment -name TOP_LEVEL_ENTITY $top_module

# ---- add sources ----
foreach src [split $rtl_files ","] {
    if {[regexp {\.v$|\.sv$}     $src]} { set_global_assignment -name SYSTEMVERILOG_FILE $src }
    if {[regexp {\.vhd$|\.vhdl$} $src]} { set_global_assignment -name VHDL_FILE $src }
}

# ---- constraints ----
if {$sdc_file ne ""} {
    set_global_assignment -name SDC_FILE $sdc_file
}

# ---- compile flags (analysis & synthesis only) ----
set_global_assignment -name OPTIMIZATION_MODE "HIGH PERFORMANCE EFFORT"

# ---- run synthesis (map) ----
execute_module -tool map

# ---- emit JSON summary ----
load_package report
load_report
set wns 0.0
set tns 0.0
catch {
    set wns [get_timing_analysis_summary_panel_data -row 0 -panel_name "Slack" -col 1]
}
set f [open $out_dir/synth_summary.json w]
puts $f "{"
puts $f "  \"stage\":    \"synth_map\","
puts $f "  \"part\":     \"$part\","
puts $f "  \"wns_ns\":   $wns,"
puts $f "  \"tns_ns\":   $tns"
puts $f "}"
close $f
unload_report

post_message "INFO: quartus synthesis (map) done"
project_close
