from pygears.core.hier_node import HierVisitorBase
from pygears.conf import reg_inject, Inject, MayInject, bind
from .gtkwave_intf import GtkWave
from pygears.sim.modules.verilator import SimVerilated
import fnmatch
import os
import re

verilator_waves = []


class VerilatorWave:
    def __init__(self, sim_module, verilator_intf):
        self.signal_name_map = {}
        self.sim_module = sim_module
        self.path_prefix = '.'.join(
            ['TOP', sim_module.wrap_name])
        self.verilator_intf = verilator_intf

        verilator_vcd = sim_module.trace_fn
        verilator_intf.command(f'gtkwave::loadFile {verilator_vcd}')
        self.signal_name_map = self.make_relative_signal_name_map(
            self.path_prefix, verilator_intf.command('list_signals'))
        verilator_intf.command(f'gtkwave::setZoomFactor -7')

    def make_relative_signal_name_map(self, path_prefix, signal_list):
        signal_name_map = {}
        for sig_name in signal_list.split('\n'):
            sig_name = sig_name.strip()

            basename = re.search(
                fr"{path_prefix}\.({self.sim_module.svmod.sv_inst_name}\..*)",
                sig_name)

            if basename:
                signal_name_map[basename.group(1)] = sig_name

        return signal_name_map

    def get_signals_for_intf(self, rtl_intf):
        signals = fnmatch.filter(self.signal_name_map.keys(), rtl_intf.name + '*')
        return [self.signal_name_map[s] for s in signals]


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
def add_gear_to_wave(gear,
                     gtkwave=Inject('viewer/gtkwave'),
                     vcd=Inject('VCD'),
                     outdir=Inject('sim/artifact_dir')):

    gear_fn = gear.name.replace('/', '_')
    gtkw = os.path.join(outdir, f'{gear_fn}.gtkw')
    gtkwave.command_nb(f'gtkwave::loadFile {gtkw}')
