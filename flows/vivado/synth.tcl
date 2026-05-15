# =====================================================================
# ROBIN-FPGA: Vivado synthesis flow
# Invoked as:
#   vivado -mode batch -source flows/vivado/synth.tcl \
#          -tclargs --rtl design.v --part xcve2302-sfva784-2MP-e-S \
#                   --xdc constraints.xdc --strategy Performance_Explore \
#                   --out runs/synth/
# =====================================================================

# ---- parse args ----
set rtl_files     ""
set part          ""
set xdc_file      ""
set strategy      "Default"
set out_dir       "./synth_out"
set top_module    "top"
set generic_args  ""

for {set i 0} {$i < [llength $argv]} {incr i} {
    set arg [lindex $argv $i]
    switch -exact -- $arg {
        "--rtl"      { incr i; set rtl_files [lindex $argv $i] }
        "--part"     { incr i; set part [lindex $argv $i] }
        "--xdc"      { incr i; set xdc_file [lindex $argv $i] }
        "--strategy" { incr i; set strategy [lindex $argv $i] }
        "--out"      { incr i; set out_dir [lindex $argv $i] }
        "--top"      { incr i; set top_module [lindex $argv $i] }
        "--generic"  { incr i; set generic_args [lindex $argv $i] }
        default      { puts "WARN: unknown arg $arg" }
    }
}

if {$rtl_files eq "" || $part eq ""} {
    puts "ERROR: --rtl and --part are required"
    exit 1
}

file mkdir $out_dir

# ---- create project ----
create_project -in_memory -part $part

# ---- add sources ----
foreach src [split $rtl_files ","] {
    if {[regexp {\.v$|\.sv$|\.vh$} $src]} {
        read_verilog $src
    } elseif {[regexp {\.vhd$|\.vhdl$} $src]} {
        read_vhdl $src
    } else {
        puts "WARN: unknown source extension: $src"
    }
}

# ---- constraints ----
if {$xdc_file ne ""} {
    read_xdc $xdc_file
}

# ---- synthesize ----
set synth_args [list -top $top_module -part $part -directive $strategy]
if {$generic_args ne ""} {
    foreach gen [split $generic_args ","] {
        lappend synth_args -generic $gen
    }
}

puts "INFO: synth_design $synth_args"
eval synth_design $synth_args

# ---- opt_design ----
opt_design -directive ExploreWithRemap

# ---- reports ----
report_timing_summary    -file $out_dir/post_synth_timing.rpt -warn_on_violation
report_utilization       -file $out_dir/post_synth_util.rpt   -hierarchical
report_power             -file $out_dir/post_synth_power.rpt
write_checkpoint -force  $out_dir/post_synth.dcp

# ---- emit a small JSON summary for the python wrapper ----
set wns [get_property SLACK [get_timing_paths -max_paths 1 -setup]]
set tns [get_property TNS_TOTAL_ENDPOINT_SLACK [current_design]]
set f [open $out_dir/synth_summary.json w]
puts $f "{"
puts $f "  \"stage\":      \"synth\","
puts $f "  \"part\":       \"$part\","
puts $f "  \"strategy\":   \"$strategy\","
puts $f "  \"wns_ns\":     $wns,"
puts $f "  \"tns_ns\":     $tns"
puts $f "}"
close $f

puts "INFO: synthesis done; checkpoint at $out_dir/post_synth.dcp"
