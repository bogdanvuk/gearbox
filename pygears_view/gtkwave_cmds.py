from pygears.conf import reg_inject, Inject
import itertools
import os


@reg_inject
def list_signal_names(graph=Inject('viewer/graph')):
    resp = graph.gtkwave.command('gtkwave::getNumFacs')
    resp = graph.gtkwave.command('gtkwave::getFacName 1')
    print(f"gtkwave::getNumFacs -> {resp}")


@reg_inject
def add_gear_to_wave(gear,
                     graph=Inject('viewer/graph'),
                     vcd=Inject('VCD'),
                     outdir=Inject('sim/artifact_dir')):
    # for i in range(40):
    #     resp = graph.gtkwave.command(f'gtkwave::getFacName {i}')
    #     print(f"gtkwave::getNumFacs -> {resp}")

    gear_fn = gear.name.replace('/', '_')
    gtkw = os.path.join(outdir, f'{gear_fn}.gtkw')
    resp = graph.gtkwave.command(f'gtkwave::loadFile {gtkw}')
    print(f"gtkwave::loadFile -> {resp}")

    # siglist = []
    # gear_vcd_scope = gear.name[1:].replace('/', '.')
    # for p in itertools.chain(gear.out_ports, gear.in_ports):

    #     scope = '.'.join([gear_vcd_scope, p.basename])
    #     siglist.extend([f'{scope}.valid', f'{scope}.ready', f'{scope}.data/*'])

    # print(siglist)
    # resp = graph.gtkwave.command(
    #     f'gtkwave::addSignalsFromList {{ {" ".join(siglist)} }}')

    # print(f"gtkwave::addSignalsFromList -> {resp}")
