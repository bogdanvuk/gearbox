from pygears.core.hier_node import HierVisitorBase
from pygears.conf import reg_inject, Inject, MayInject, bind
from .gtkwave_intf import GtkWave
from pygears.sim.modules.verilator import SimVerilated
import os
import re

signal_names = {}
verilated_modules = []


@reg_inject
def find_verilated_modules(top=Inject('gear/hier_root')):
    class VerilatedVisitor(HierVisitorBase):
        @reg_inject
        def __init__(self, sim_map=Inject('sim/map')):
            self.sim_map = sim_map
            self.verilated_modules = []

        def Gear(self, module):
            if isinstance(self.sim_map.get(module, None), SimVerilated):
                self.verilated_modules.append(self.sim_map[module])
                return True

    v = VerilatedVisitor()
    v.visit(top)
    return v.verilated_modules


@reg_inject
def load(
        main=Inject('viewer/main'),
        outdir=MayInject('sim/artifact_dir'),
        viewer=Inject('viewer/gtkwave')):
    print("Loading...")
    main.buffers['gtkwave'] = viewer.gtkwave_widget
    if outdir:
        verilated_modules.extend(find_verilated_modules())
        # pyvcd = os.path.abspath(os.path.join(outdir, 'pygears.vcd'))
        verilator_vcd = verilated_modules[0].trace_fn
        # viewer.command(f'gtkwave::loadFile {pyvcd}')
        viewer.command(f'gtkwave::loadFile {verilator_vcd}')

        prefix = '.'.join([
            'TOP', verilated_modules[0].wrap_name,
            verilated_modules[0].svmod.sv_inst_name
        ])

        sig_list = viewer.command('list_signals')
        for sig_name in sig_list.split('\n'):
            sig_name = sig_name.strip()

            basename = re.search(prefix + "\." + r"(.*)", sig_name)
            if basename:
                signal_names[basename.group(1)] = sig_name

        print(signal_names)


def gtkwave():
    viewer = GtkWave()
    bind('viewer/gtkwave', viewer)
    viewer.initialized.connect(load)


@reg_inject
def list_signal_names(gtkwave=Inject('viewer/gtkwave')):
    resp = gtkwave.command('test_proc')
    signal_names.extend()
    print("Response:   ")
    print(resp)

    # resp = gtkwave.command('gtkwave::getNumFacs')

    # for i in range(int(resp)):
    #     resp = gtkwave.command(f'gtkwave::getFacName {i}')
    #     print(resp)


@reg_inject
def add_gear_to_wave(gear,
                     gtkwave=Inject('viewer/gtkwave'),
                     vcd=Inject('VCD'),
                     outdir=Inject('sim/artifact_dir')):
    # for i in range(40):
    #     resp = graph.gtkwave.command(f'gtkwave::getFacName {i}')
    #     print(f"gtkwave::getNumFacs -> {resp}")

    gear_fn = gear.name.replace('/', '_')
    gtkw = os.path.join(outdir, f'{gear_fn}.gtkw')
    resp = gtkwave.command(f'gtkwave::loadFile {gtkw}')
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
