proc list_signals {} {
    set nfacs [ gtkwave::getNumFacs ]
    for {set i 0} {$i < $nfacs } {incr i} {
        set facname [ gtkwave::getFacName $i ]
        puts $facname
    }
}

# proc get_values {} {
#     for {set i 0} {$i < 1 } {incr i} {
#         puts [gtkwave::signalChangeList rng.dout.data/data -dir backward -max 1]
#     }
# }

proc get_values {signals} {
    set end_time_value [ gtkwave::getWindowEndTime ]
    foreach s $signals {
        set valid_val [gtkwave::signalChangeList ${s}_valid -start_time $end_time_value -max 1]
        set ready_val [gtkwave::signalChangeList ${s}_ready -start_time $end_time_value -max 1]
        puts [format "%s %s" [lindex $valid_val 1] [lindex $ready_val 1]]
    }
}
