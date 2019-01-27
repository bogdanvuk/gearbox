from PySide2 import QtCore
from functools import partial
import collections

from pygears.sim.modules import SimVerilated
from pygears.sim import timestep
from .node_model import find_cosim_modules
from pygears.core.hier_node import HierVisitorBase
from pygears.conf import Inject, reg_inject, MayInject, bind, registry
from pygears.rtl.gear import rtl_from_gear_port
from typing import NamedTuple
from .gtkwave_intf import GtkWaveWindow
from .graph import GraphVisitor
from .layout import active_buffer, Buffer
import fnmatch
import os
import re


class PipeNotTraced(Exception):
    pass


def active_intf():
    active_buffer()


class VerilatorVCDMap:
    @reg_inject
    def __init__(self,
                 sim_module,
                 gtkwave_intf,
                 rtl_map=Inject('rtl/gear_node_map')):
        self.gtkwave_intf = gtkwave_intf
        self.sim_module = sim_module
        self.rtl_node = rtl_map[self.sim_module.gear]
        self.path_prefix = '.'.join(['TOP', sim_module.wrap_name])
        self.pipe_signals = {}
        self.signal_name_map = {}

    @property
    def name(self):
        return self.sim_module.name

    @property
    def vcd_fn(self):
        return self.sim_module.trace_fn

    def pipe_basename(self, pipe):
        pipe_name_stem = pipe.name[len(self.rtl_node.parent.name) + 1:]
        return pipe_name_stem.replace('/', '.')

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

        if not self.rtl_node.is_descendent(pipe.intf):
            return

        signals = fnmatch.filter(self.signal_name_map.keys(),
                                 self.pipe_basename(pipe) + '_*')
        return [self.signal_name_map[s] for s in signals]


def gtkwave():
    status = GtkWave()
    bind('viewer/gtkwave', status)
    status.update()


class Signals(NamedTuple):
    ready: str
    valid: str


class GraphPipeCollector(HierVisitorBase):
    def __init__(self, vcd_map):
        self.vcd_pipes = {}
        self.vcd_map = vcd_map

    def PipeModel(self, pipe):
        if pipe not in self.vcd_pipes:
            try:
                all_sigs = self.vcd_map.get_signals_for_pipe(pipe)
                # print(f'Pipe: {pipe} ({rtl_intf.name}) -> {all_sigs}')

                stem = ''
                for s in all_sigs:
                    if s.endswith('_valid'):
                        stem = s[:-6]
                        break

                if stem:
                    self.vcd_pipes[pipe] = stem
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

        for m in find_cosim_modules():
            if not isinstance(m, SimVerilated):
                continue

            if hasattr(m, 'shmid'):
                trace_fn = m.shmid
            else:
                trace_fn = m.trace_fn

            instance = GtkWaveWindow(trace_fn)
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
        pipe_intf = self.pipe_gtkwave_intf(pipe)
        if pipe_intf is None:
            raise PipeNotTraced

        return pipe_intf.show_pipe(pipe)

    def update(self):
        for w in self.graph_intfs:
            w.update()


class GtkWaveBuffer(Buffer):
    def __init__(self, intf, instance, name):
        self.intf = intf
        self.name = name
        self.instance = instance
        self.instance.initialized.connect(self.load)
        self.window = None

    @reg_inject
    def load(self, main=Inject('viewer/main')):
        main.add_buffer(self)
        # main.add_buffer(self.name, self.window.widget)

    def activate(self):
        super().activate()
        self.instance.widget.activateWindow()
        # self.instance.gtkwave_win.setKeyboardGrabEnabled(True)

    def deactivate(self):
        super().deactivate()
        # self.instance.gtkwave_win.setKeyboardGrabEnabled(False)

    @property
    def view(self):
        return self.instance.widget

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
        self.should_update = False
        self.updating = False

    def has_pipe_wave(self, pipe):
        return pipe in self.pipe_collect.vcd_pipes

    def show_pipe(self, pipe):

        struct_sigs = collections.defaultdict(dict)
        sig_names = []

        prefix = (
            self.vcd_map.path_prefix + '.' + self.vcd_map.pipe_basename(pipe))

        intf_name = pipe.name.replace('.', '/')
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
                    if p not in place:
                        place[p] = {}

                    place = place[p]

                place[path[-1]] = s

        commands.append('gtkwave::addSignalsFromList {' + " ".join(sig_names) +
                        '}')

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
        self.gtkwave_intf.command(commands)

        return intf_name

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

    @property
    def cmd_id(self):
        return id(self) & 0xffff

    def gtkwave_resp(self, ret, cmd_id):
        if cmd_id != self.cmd_id:
            return

        ts = timestep()
        if ts is None:
            ts = 0

        gtkwave_timestep = int(ret) // 10
        self.gtkwave_intf.response.disconnect(self.gtkwave_resp)

        if ts - gtkwave_timestep > 1000:
            self.should_update = False
            self.gtkwave_intf.response.connect(self.gtkwave_resp)
            self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
            return

        signal_names = [(pipe, name)
                        for pipe, name in self.pipe_collect.vcd_pipes.items()
                        if pipe.view.isVisible()]

        for i in range(0, len(signal_names), 20):

            cur_slice = slice(i, min(len(signal_names), i + 20))
            cur_names = signal_names[cur_slice]

            ret = self.gtkwave_intf.command(
                f'get_values [list {" ".join(s[1] for s in cur_names)}]')
            rtl_status = ret.split('\n')

            # assert len(rtl_status) == (cur_slice.stop - cur_slice.start)
            if len(rtl_status) != (cur_slice.stop - cur_slice.start):
                continue

            for wave_status, (pipe, _) in zip(rtl_status, cur_names):
                self.update_rtl_intf(pipe, wave_status.strip())

        if self.should_update:
            self.should_update = False
            self.gtkwave_intf.response.connect(self.gtkwave_resp)
            self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
        else:
            self.updating = False

    def update(self):
        if not self.loaded:
            # ret = self.gtkwave_intf.command(
            #     f'gtkwave::loadFile {self.vcd_map.vcd_fn}')

            # if "File load failure" in ret:
            #     return False

            self.gtkwave_intf.command(f'gtkwave::stripGUI')
            self.gtkwave_intf.command(f'gtkwave::setZoomFactor -7')
            self.pipe_collect.visit(self.graph)
            self.loaded = True
            self.vcd_loaded.emit()

        if not self.updating:
            self.should_update = False
            self.updating = True
            self.gtkwave_intf.response.connect(self.gtkwave_resp)
            self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
        else:
            self.should_update = True
