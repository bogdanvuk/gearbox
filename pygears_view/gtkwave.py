from pygears.core.hier_node import HierVisitorBase

from pygears.conf import Inject, reg_inject
from pygears.rtl.gear import rtl_from_gear_port
from typing import NamedTuple
from pygears.conf import reg_inject, Inject, MayInject, bind
from .gtkwave_intf import GtkWave
from .graph import GraphVisitor
from pygears.sim.modules.verilator import SimVerilated
import fnmatch
import os
import re


class VerilatorWave:
    @reg_inject
    def __init__(self, sim_module, verilator_intf=Inject('viewer/gtkwave')):
        self.signal_name_map = {}
        self.sim_module = sim_module
        self.path_prefix = '.'.join(['TOP', sim_module.wrap_name])
        self.verilator_intf = verilator_intf
        self.loaded = False

    def load_vcd(self):
        verilator_vcd = self.sim_module.trace_fn
        ret = self.verilator_intf.command(f'gtkwave::loadFile {verilator_vcd}')
        if "File load failure" not in ret:
            self.loaded = True
        else:
            return False

        self.signal_name_map = self.make_relative_signal_name_map(
            self.path_prefix, self.verilator_intf.command('list_signals'))
        self.verilator_intf.command(f'gtkwave::setZoomFactor -7')

        return True

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
        signals = fnmatch.filter(self.signal_name_map.keys(),
                                 rtl_intf.name + '*')
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
    bind('viewer/gtkwave_status', GraphGtkWaveStatus())

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


class Signals(NamedTuple):
    ready: str
    valid: str


class GraphPipeCollector(GraphVisitor):
    def __init__(self, verilator_waves):
        self.rtl_intfs = {}
        self.verilator_wave = verilator_waves[0]

    def pipe(self, pipe):
        if pipe not in self.rtl_intfs:
            port = pipe.output_port.model
            rtl_port = rtl_from_gear_port(port)
            if rtl_port is None:
                return

            rtl_intf = rtl_port.consumer
            if rtl_intf is None:
                return

            try:
                all_sigs = self.verilator_wave.get_signals_for_intf(rtl_intf)
                # print(f'Pipe: {pipe} ({rtl_intf.name}) -> {all_sigs}')

                stem = ''
                for s in all_sigs:
                    if s.endswith('_valid'):
                        stem = s[:-6]
                        break

                if stem:
                    self.rtl_intfs[pipe] = stem
            except:
                pass


class GraphGtkWaveStatus:
    @reg_inject
    def __init__(self,
                 graph=Inject('viewer/graph'),
                 sim_bridge=MayInject('viewer/sim_bridge')):
        self.graph = graph

        if sim_bridge:
            sim_bridge.sim_refresh.connect(self.update)

        self.verilator_waves = [
            VerilatorWave(m) for m in find_verilated_modules()
        ]

        self.pipe_collect = GraphPipeCollector(self.verilator_waves)

    def update_rtl_intf(self, pipe, wave_status):
        if wave_status == '1 0':
            status = 'active'
        elif wave_status == '0 1':
            status = 'waited'
        elif wave_status == '1 1':
            status = 'handshaked'
        else:
            status = 'empty'

        pipe.set_status(status)

    @reg_inject
    def update(self, gtkwave=Inject('viewer/gtkwave')):
        for v in self.verilator_waves:
            if not v.loaded:
                if v.load_vcd():
                    self.pipe_collect.visit(self.graph.top)

        if not all(v.loaded for v in self.verilator_waves):
            return

        gtkwave.command(f'gtkwave::reLoadFile')

        signal_names = list(self.pipe_collect.rtl_intfs.values())

        ret = gtkwave.command(f'get_values [list {" ".join(signal_names)}]')
        self.rtl_status = ret.split('\n')

        # assert len(self.rtl_status) == len(self.pipe_collect.rtl_intfs)
        if len(self.rtl_status) != len(self.pipe_collect.rtl_intfs):
            return

        for wave_status, rtl_intf in zip(self.rtl_status,
                                         self.pipe_collect.rtl_intfs):
            self.update_rtl_intf(rtl_intf, wave_status.strip())
