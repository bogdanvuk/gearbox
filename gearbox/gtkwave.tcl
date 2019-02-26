set TR_HIGHLIGHT            [expr 1 << 0]
set TR_HEX                  [expr 1 << 1]
set TR_DEC                  [expr 1 << 2]
set TR_BIN                  [expr 1 << 3]
set TR_OCT                  [expr 1 << 4]
set TR_RJUSTIFY             [expr 1 << 5]
set TR_INVERT               [expr 1 << 6]
set TR_REVERSE              [expr 1 << 7]
set TR_EXCLUDE              [expr 1 << 8]
set TR_BLANK                [expr 1 << 9]
set TR_SIGNED               [expr 1 << 10]
set TR_ASCII                [expr 1 << 11]
set TR_COLLAPSED            [expr 1 << 12]
set TR_FTRANSLATED          [expr 1 << 13]
set TR_PTRANSLATED          [expr 1 << 14]
set TR_ANALOG_STEP          [expr 1 << 15]
set TR_ANALOG_INTERPOLATED  [expr 1 << 16]
set TR_ANALOG_BLANK_STRETCH [expr 1 << 17]
set TR_REAL                 [expr 1 << 18]
set TR_ANALOG_FULLSCALE     [expr 1 << 19]
set TR_ZEROFILL             [expr 1 << 20]
set TR_ONEFILL              [expr 1 << 21]
set TR_CLOSED               [expr 1 << 22]
set TR_GRP_BEGIN            [expr 1 << 23]
set TR_GRP_END              [expr 1 << 24]
set TR_BINGRAY              [expr 1 << 25]
set TR_GRAYBIN              [expr 1 << 26]
set TR_REAL2BITS            [expr 1 << 27]
set TR_TTRANSLATED          [expr 1 << 28]
set TR_POPCNT               [expr 1 << 29]
set TR_FPDECSHIFT           [expr 1 << 30]

proc list_signals {} {
    set nfacs [ gtkwave::getNumFacs ]
    for {set i 0} {$i < $nfacs } {incr i} {
        set facname [ gtkwave::getFacName $i ]
        puts $facname
    }
}

proc list_traces {} {
    set total_traces [ gtkwave::getTotalNumTraces ]
    for {set i 0} {$i < $total_traces } {incr i} {
        set trace_name [ gtkwave::getTraceNameFromIndex $i ]
        puts $trace_name
    }
}

proc select_trace_by_name {name} {
    set total_traces [ gtkwave::getTotalNumTraces ]
    set name [string trim $name]
    for {set i 0} {$i < $total_traces } {incr i} {
        set trace_name [ gtkwave::getTraceNameFromIndex $i ]
        # puts $trace_name
        if {$name == $trace_name} {
            # puts "Selected $name"
            gtkwave::setTraceHighlightFromIndex $i on
            break
        }
    }
}

# proc get_values {} {
#     for {set i 0} {$i < 1 } {incr i} {
#         puts [gtkwave::signalChangeList rng.dout.data/data -dir backward -max 1]
#     }
# }

proc list_values {signals} {
    set end_time_value [ gtkwave::getWindowEndTime ]
    puts "End time: $end_time_value"
    foreach s $signals {
        if { [catch {
            set valid_val [gtkwave::signalChangeList ${s}_valid -start_time $end_time_value -max 1]
            set ready_val [gtkwave::signalChangeList ${s}_ready -start_time $end_time_value -max 1]
            puts [format "%s: %s - %s " $s $valid_val $ready_val]
        } err ]} {
            puts "$s: 0 0"
        }
    }
}

proc trace_up {} {
    set total_traces [ gtkwave::getTotalNumTraces ]

    set skip_group_lvls 0
    set highlight_found 0
    for {set i [expr $total_traces - 1]} {$i >= 0 } {incr i -1} {
        set trace_flags [ gtkwave::getTraceFlagsFromIndex $i ]
        set trace_name [ gtkwave::getTraceNameFromIndex $i ]

        set trace_flags [ gtkwave::getTraceFlagsFromIndex $i ]

        if {($trace_flags & $::TR_GRP_BEGIN) && $skip_group_lvls && ($trace_flags & $::TR_CLOSED)} {
            set skip_group_lvls [expr $skip_group_lvls - 1]
        }

        # puts [format "State %s: %d, %d" $trace_name $skip_group_lvls $highlight_found]

        if {!($skip_group_lvls) && !($trace_flags & $::TR_GRP_END)} {
            if {$highlight_found} {
                # puts "Hihglihgting $i"
                gtkwave::/Edit/UnHighlight_All
                gtkwave::setTraceHighlightFromIndex $i on
                return
            }

            if {$trace_flags & $::TR_HIGHLIGHT} {
                set highlight_found 1
            }
        }

        if {($trace_flags & $::TR_GRP_END) && ($skip_group_lvls || ($trace_flags & $::TR_CLOSED) || $highlight_found)} {
            set skip_group_lvls [expr $skip_group_lvls + 1]
        }
    }

    # puts "Hihglihgting [expr $total_traces - 1]"
    gtkwave::/Edit/UnHighlight_All
    gtkwave::setTraceHighlightFromIndex [expr $total_traces - 1] on
}

proc trace_down {} {
    set total_traces [ gtkwave::getTotalNumTraces ]
    # puts "Total traces $total_traces"

    # for {set i 0} {$i < $total_traces } {incr i} {
    #     set trace_flags [ gtkwave::getTraceFlagsFromIndex $i ]
    #     set trace_name [ gtkwave::getTraceNameFromIndex $i ]

    #     puts [format "Trace %s: %x" $trace_name $trace_flags]
    # }

    # puts "----------------------------------------------"

    set skip_group_lvls 0
    set highlight_found 0
    for {set i 0} {$i < $total_traces } {incr i} {
        set trace_flags [ gtkwave::getTraceFlagsFromIndex $i ]
        # set trace_name [ gtkwave::getTraceNameFromIndex $i ]

        # puts [format "State %s: %d, %d" $trace_name $skip_group_lvls $highlight_found]

        if {$highlight_found && !($skip_group_lvls)} {
            puts "Hihglihgting $i"
            gtkwave::/Edit/UnHighlight_All
            gtkwave::setTraceHighlightFromIndex $i on
            return
        }

        if {$trace_flags & $::TR_HIGHLIGHT} {
            set highlight_found 1
        }

        if {($trace_flags & $::TR_GRP_BEGIN) && ($skip_group_lvls || ($trace_flags & $::TR_CLOSED)) } {
            set skip_group_lvls [expr $skip_group_lvls + 1]
        }

        if {($trace_flags & $::TR_GRP_END) && ($skip_group_lvls && ($trace_flags & $::TR_CLOSED))} {
            set skip_group_lvls [expr $skip_group_lvls - 1]
        }
    }

    puts "Hihglihgting 0"
    gtkwave::/Edit/UnHighlight_All
    gtkwave::setTraceHighlightFromIndex 0 on
}

proc get_values {timestep signals} {
    foreach s $signals {
        if { [catch {
            set valid_val [gtkwave::signalValueAt ${s}valid $timestep]
            set ready_val [gtkwave::signalValueAt ${s}ready $timestep]
            puts [format "%s %s" $valid_val $ready_val]
        } err ]} {
            puts "0 0"
        }
    }
}

proc set_marker_if_needed {timestep} {
    if {[gtkwave::getMarker] != $timestep} {
        gtkwave::setMarker $timestep
        # gtkwave::setWindowStartTime [expr $timestep - 10]
    }
}
