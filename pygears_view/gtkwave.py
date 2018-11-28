from pygears.core.hier_node import HierVisitorBase
from pygears.conf import reg_inject, Inject, MayInject, bind
from .gtkwave_intf import GtkWave
from pygears.sim.modules.verilator import SimVerilated
import os
import re

verilator_waves = []


class VerilatorWave:
    def __init__(self, sim_module, verilator_intf):
        self.signal_names = {}
        self.sim_module = sim_module
        self.path_prefix = '.'.join(
            ['TOP', sim_module.wrap_name, ])
        self.verilator_intf = verilator_intf

        verilator_vcd = sim_module.trace_fn
        verilator_intf.command(f'gtkwave::loadFile {verilator_vcd}')
        self.signal_name_map = self.make_relative_signal_name_map(
            self.path_prefix, verilator_intf.command('list_signals'))

        print(self.signal_name_map)

    def make_relative_signal_name_map(self, path_prefix, signal_list):
        signal_name_map = {}
        for sig_name in signal_list.split('\n'):
            sig_name = sig_name.strip()

            basename = re.search(fr"{path_prefix}\.({self.sim_module.svmod.sv_inst_name}\..*)", sig_name)
            if basename:
                signal_name_map[basename.group(1)] = sig_name

        return signal_name_map


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
    verilator_waves.extend(
        [VerilatorWave(m, viewer) for m in find_verilated_modules()])

    # if outdir:
    #     pyvcd = os.path.abspath(os.path.join(outdir, 'pygears.vcd'))
    #     viewer.command(f'gtkwave::loadFile {pyvcd}')


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
