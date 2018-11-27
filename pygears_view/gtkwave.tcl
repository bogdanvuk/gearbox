proc list_signals {} {
    set nfacs [ gtkwave::getNumFacs ]
    for {set i 0} {$i < $nfacs } {incr i} {
        set facname [ gtkwave::getFacName $i ]
        puts $facname
    }
}
