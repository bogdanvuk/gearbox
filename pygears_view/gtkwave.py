from PySide2 import QtCore
from functools import partial
import collections
from pygears.core.hier_node import HierVisitorBase

from pygears.conf import Inject, reg_inject, MayInject, bind
from pygears.rtl.gear import rtl_from_gear_port
from typing import NamedTuple
from .gtkwave_intf import GtkWaveWindow
from .graph import GraphVisitor
from .main_window import active_buffer
from pygears.sim.modules.verilator import SimVerilated
import fnmatch
import os
import re


def active_intf():
    active_buffer()


class VerilatorVCDMap:
    def __init__(self, sim_module, gtkwave_intf):
        self.gtkwave_intf = gtkwave_intf
        self.sim_module = sim_module
        self.path_prefix = '.'.join(['TOP', sim_module.wrap_name])
        self.pipe_signals = {}
        self.signal_name_map = {}

    @property
    def name(self):
        return self.sim_module.name

    @property
    def vcd_fn(self):
        return self.sim_module.trace_fn

    def pipe_rtl_intf(self, pipe):
        rtl_port = rtl_from_gear_port(pipe.output_port.model)
        if rtl_port is None:
            return None

        return rtl_port.consumer

    def pipe_basename(self, pipe):
        return f'{self.path_prefix}.{self.pipe_rtl_intf(pipe).name}'

    def make_relative_signal_name_map(self, path_prefix, signal_list):
        signal_name_map = {}
        for sig_name in signal_list.split('\n'):
            sig_name = sig_name.strip()

            basename = re.search(
                r"{0}\.({1}\..*)".format(
                    path_prefix, self.sim_module.svmod.sv_inst_name), sig_name)

            if basename:
                signal_name_map[basename.group(1)] = sig_name

        return signal_name_map

    def get_signals_for_pipe(self, pipe):
        if pipe in self.pipe_signals:
            return self.pipe_signals[pipe]

        if not self.signal_name_map:
            self.signal_name_map = self.make_relative_signal_name_map(
                self.path_prefix, self.gtkwave_intf.command('list_signals'))

        signals = fnmatch.filter(self.signal_name_map.keys(),
                                 self.pipe_rtl_intf(pipe).name + '_*')
        return [self.signal_name_map[s] for s in signals]


# class VerilatorWave:
#     @reg_inject
#     def __init__(self, sim_module):
#         self.signal_name_map = {}
#         self.sim_module = sim_module
#         self.path_prefix = '.'.join(['TOP', sim_module.wrap_name])
#         self.gtkwave_intf = GtkWave()
#         self.gtkwave_intf.initialized.connect(self.load)
#         self.loaded = False

#     def load(self, main=Inject('viewer/main')):
#         main.add_buffer(
#             f'gtkwave - {self.sim_module.name}', self.gtkwave_intf.widget)

#     def load_vcd(self):
#         verilator_vcd = self.sim_module.trace_fn
#         ret = self.gtkwave_intf.command(f'gtkwave::loadFile {verilator_vcd}')
#         if "File load failure" not in ret:
#             self.loaded = True
#         else:
#             return False

#         self.signal_name_map = self.make_relative_signal_name_map(
#             self.path_prefix, self.gtkwave_intf.command('list_signals'))
#         self.gtkwave_intf.command(f'gtkwave::setZoomFactor -7')

#         return True

#     def intf_basename(self, rtl_intf):
#         return f'{self.path_prefix}.{rtl_intf.name}'

#     def make_relative_signal_name_map(self, path_prefix, signal_list):
#         signal_name_map = {}
#         for sig_name in signal_list.split('\n'):
#             sig_name = sig_name.strip()

#             basename = re.search(
#                 fr"{path_prefix}\.({self.sim_module.svmod.sv_inst_name}\..*)",
#                 sig_name)

#             if basename:
#                 signal_name_map[basename.group(1)] = sig_name

#         return signal_name_map

#     def get_signals_for_intf(self, rtl_intf):
#         signals = fnmatch.filter(self.signal_name_map.keys(),
#                                  rtl_intf.name + '_*')
#         return [self.signal_name_map[s] for s in signals]


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


def gtkwave():
    status = GtkWave()
    bind('viewer/gtkwave', status)
    status.update()


class Signals(NamedTuple):
    ready: str
    valid: str


class GraphPipeCollector(GraphVisitor):
    def __init__(self, vcd_map):
        self.rtl_intfs = {}
        self.vcd_map = vcd_map

    def pipe(self, pipe):
        if pipe not in self.rtl_intfs:
            try:
                all_sigs = self.vcd_map.get_signals_for_pipe(pipe)
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


class GtkWave:
    @reg_inject
    def __init__(self,
                 graph=Inject('viewer/graph_model'),
                 sim_bridge=MayInject('viewer/sim_bridge')):
        super().__init__()
        self.graph = graph

        if sim_bridge:
            sim_bridge.sim_refresh.connect(self.update)

        self.graph_intfs = []
        self.instances = []
        self.buffers = []

        for m in find_verilated_modules():
            instance = GtkWaveWindow()
            vcd_map = VerilatorVCDMap(m, instance)
            intf = GtkWaveGraphIntf(
                vcd_map, instance, graph=graph[m.gear.name[1:]])

            buffer = GtkWaveBuffer(intf, instance, f'gtkwave - {vcd_map.name}')

            self.graph_intfs.append(intf)
            self.instances.append(instance)
            self.buffers.append(buffer)

    def pipe_gtkwave_intf(self, pipe):
        for intf in self.graph_intfs:
            if intf.has_pipe_wave(pipe):
                return intf

    def pipe_gtkwave_instance(self, pipe):
        for intf, inst in zip(self.graph_intfs, self.instances):
            if intf.has_pipe_wave(pipe):
                return inst

    def show_pipe(self, pipe):
        return self.pipe_gtkwave_intf(pipe).show_pipe(pipe)

    def update(self):
        for w in self.graph_intfs:
            w.update()


class GtkWaveBuffer:
    def __init__(self, intf, window, name):
        self.intf = intf
        self.name = name
        self.window = window
        self.window.initialized.connect(self.load)

    @reg_inject
    def load(self, main=Inject('viewer/main')):
        pass
        # main.add_buffer(self)
        # main.add_buffer(self.name, self.window.widget)

    @property
    def view(self):
        return self.window.widget

    @property
    def domain(self):
        return 'gtkwave'


class GtkWaveGraphIntf(QtCore.QObject):
    vcd_loaded = QtCore.Signal()

    @reg_inject
    def __init__(self,
                 vcd_map,
                 gtkwave_intf,
                 graph=Inject('viewer/graph_model')):
        super().__init__()
        self.graph = graph
        self.vcd_map = vcd_map
        self.gtkwave_intf = gtkwave_intf
        self.loaded = False
        self.pipe_collect = GraphPipeCollector(vcd_map)
        self.pipes_on_wave = {}

    def has_pipe_wave(self, pipe):
        return pipe in self.pipe_collect.rtl_intfs

    def show_pipe(self, pipe):

        struct_sigs = collections.defaultdict(dict)
        sig_names = []

        prefix = self.vcd_map.pipe_basename(pipe)

        rtl_intf = self.vcd_map.pipe_rtl_intf(pipe)
        intf_name = rtl_intf.name.replace('.', '/')
        status_sig = intf_name + '_state'
        valid_sig = prefix + '_valid'
        ready_sig = prefix + '_ready'

        self.pipes_on_wave[pipe] = intf_name

        commands = []

        dti_translate_path = os.path.join(
            os.path.dirname(__file__), "dti_translate.py")
        commands.append(
            f'gtkwave::addSignalsFromList {{{valid_sig} {ready_sig}}}')
        commands.append(
            f'gtkwave::highlightSignalsFromList {{{valid_sig} {ready_sig}}}')

        commands.append(f'gtkwave::/Edit/Combine_Down {{{status_sig}}}')
        commands.append(f'select_trace_by_name {{{status_sig}}}')
        commands.append('gtkwave::/Edit/Toggle_Group_Open|Close')
        commands.append(
            f'gtkwave::setCurrentTranslateTransProc "{dti_translate_path}"')
        commands.append(f'gtkwave::installTransFilter 1')

        for s in self.vcd_map.get_signals_for_pipe(pipe):
            stem = s[len(prefix):]
            if stem.startswith('_data'):
                sig_names.append(s)
                sig_name_no_width = stem.partition('[')[0]

                path = sig_name_no_width.split('.')
                place = struct_sigs
                for p in path[:-1]:
                    place = place[p]

                place[path[-1]] = s

        commands.append('gtkwave::addSignalsFromList {' + " ".join(sig_names) +
                        '}')

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
            commands.append('gtkwave::highlightSignalsFromList {' +
                            " ".join(selected) + '}')
            commands.append(f'gtkwave::/Edit/Combine_Down {name}')

        commands.append('select_trace_by_name {' + intf_name + '}')
        commands.append('gtkwave::/Edit/Toggle_Group_Open|Close')
        self.gtkwave_intf.command('\n'.join(commands))

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
        if not self.loaded:
            ret = self.gtkwave_intf.command(
                f'gtkwave::loadFile {self.vcd_map.vcd_fn}')
            if "File load failure" not in ret:
                self.loaded = True
            else:
                return False

            self.pipe_collect.visit(self.graph.view)
            self.vcd_loaded.emit()

        self.gtkwave_intf.command(f'gtkwave::reLoadFile')

        signal_names = list(self.pipe_collect.rtl_intfs.values())

        ret = self.gtkwave_intf.command(
            f'get_values [list {" ".join(signal_names)}]')
        self.rtl_status = ret.split('\n')
        # self.gtkwave.command(f'list_values [list {" ".join(signal_names)}]')

        # assert len(self.rtl_status) == len(self.pipe_collect.rtl_intfs)
        if len(self.rtl_status) != len(self.pipe_collect.rtl_intfs):
            return

        for wave_status, rtl_intf in zip(self.rtl_status,
                                         self.pipe_collect.rtl_intfs):
            self.update_rtl_intf(rtl_intf, wave_status.strip())
