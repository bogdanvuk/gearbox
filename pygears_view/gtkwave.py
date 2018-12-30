import tempfile
import collections
from pygears.core.hier_node import HierVisitorBase
from vcd.gtkw import GTKWSave

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

    def intf_basename(self, rtl_intf):
        return f'{self.path_prefix}.{rtl_intf.name}'

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
                                 rtl_intf.name + '_*')
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
    status = GraphGtkWaveStatus()
    bind('viewer/gtkwave_status', status)
    status.update()

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
                 gtkwave=Inject('viewer/gtkwave'),
                 sim_bridge=MayInject('viewer/sim_bridge')):
        self.graph = graph
        self.gtkwave = gtkwave

        if sim_bridge:
            sim_bridge.sim_refresh.connect(self.update)

        self.verilator_waves = [
            VerilatorWave(m) for m in find_verilated_modules()
        ]

        self.pipe_collect = GraphPipeCollector(self.verilator_waves)

        self.pipes_on_wave = {}

    def show_pipe(self, pipe):
        rtl_port = rtl_from_gear_port(pipe.output_port.model)
        if rtl_port is None:
            return

        rtl_intf = rtl_port.consumer
        sigs = self.verilator_waves[0].get_signals_for_intf(rtl_intf)

        struct_sigs = collections.defaultdict(dict)
        sig_names = []

        prefix = self.verilator_waves[0].intf_basename(rtl_intf)
        intf_name = rtl_intf.name.replace('.', '/')
        status_sig = prefix + '_state[1:0]'

        self.pipes_on_wave[pipe] = intf_name

        commands = []

        dti_translate_path = os.path.join(os.path.dirname(__file__), "dti_translate.py")
        commands.append(f'gtkwave::addSignalsFromList {{ {status_sig} }}')
        commands.append(f'gtkwave::highlightSignalsFromList {{ {status_sig} }}')
        commands.append(f'gtkwave::setCurrentTranslateTransProc "{dti_translate_path}"')
        commands.append(f'gtkwave::installTransFilter 1')

        # struct_sigs['_data']['state'] = status_sig

        for s in sigs:
            stem = s[len(prefix):]
            if stem.startswith('_data'):
                sig_names.append(s)
                sig_name_no_width = stem.partition('[')[0]

                path = sig_name_no_width.split('.')
                place = struct_sigs
                for p in path[:-1]:
                    place = place[p]

                place[path[-1]] = s

        commands.append('gtkwave::addSignalsFromList {' + " ".join(sig_names) + '}')

        print(sig_names)

        def dfs(name, lvl):
            if isinstance(lvl, dict):
                selected = []
                for k, v in lvl.items():
                    if isinstance(v, dict):
                        ret = yield from dfs(k, v)
                        selected.extend(ret)
                    else:
                        selected.append(v)

            else:
                selected = [lvl]

            yield name, selected
            return selected

        struct_sigs = dict(struct_sigs)

        groups = list(dfs(intf_name, struct_sigs['_data']))
        for name, selected in reversed(groups):
            commands.append('gtkwave::highlightSignalsFromList {' + " ".join(selected) + '}')
            commands.append(f'gtkwave::/Edit/Combine_Down {name}')

        commands.append('select_trace_by_name {' + intf_name + '}')
        commands.append('gtkwave::/Edit/Toggle_Group_Open|Close')
        self.gtkwave.command('\n'.join(commands))


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

    def update(self):
        for v in self.verilator_waves:
            if not v.loaded:
                if v.load_vcd():
                    self.pipe_collect.visit(self.graph.top)

        if not all(v.loaded for v in self.verilator_waves):
            return

        self.gtkwave.command(f'gtkwave::reLoadFile')

        signal_names = list(self.pipe_collect.rtl_intfs.values())

        ret = self.gtkwave.command(f'get_values [list {" ".join(signal_names)}]')
        self.rtl_status = ret.split('\n')

        # assert len(self.rtl_status) == len(self.pipe_collect.rtl_intfs)
        if len(self.rtl_status) != len(self.pipe_collect.rtl_intfs):
            return

        for wave_status, rtl_intf in zip(self.rtl_status,
                                         self.pipe_collect.rtl_intfs):
            self.update_rtl_intf(rtl_intf, wave_status.strip())
