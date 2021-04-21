from PySide2 import QtCore
import collections
import sys

from pygears import find
from .timekeep import timestep, timestep_event_register
from pygears.sim.modules import SimVerilated
from .node_model import find_cosim_modules, PipeModel, NodeModel
from pygears.core.hier_node import HierVisitorBase, HierYielderBase
from pygears.core.graph import get_source_producer
from pygears.conf import Inject, MayInject, inject, reg
from typing import NamedTuple
from .gtkwave_intf import GtkWaveWindow
from .layout import active_buffer, Buffer, LayoutPlugin
from .utils import single_shot_connect
from .dbg import dbg_connect
from functools import partial
from .gtkwave_vcd import PyGearsVCDMap, VerilatorVCDMap
import os


class ItemNotTraced(Exception):
    pass


def active_intf():
    active_buffer()


@inject
def gtkwave(graph_model_ctrl=Inject('gearbox/graph_model_ctrl')):
    graph_model_ctrl.graph_loaded.connect(gtkwave_create)
    # dbg_connect(graph_model_ctrl.graph_loaded, gtkwave_create)


@inject
def gtkwave_create(graph_model_ctrl=Inject('gearbox/graph_model_ctrl')):
    gtkwave = GtkWave()
    reg['gearbox/gtkwave/inst'] = gtkwave
    single_shot_connect(graph_model_ctrl.graph_closed, gktwave_delete)


@inject
def gktwave_delete(timekeep=Inject('gearbox/timekeep')):
    print('Gtkwave deleted')
    gtkwave = reg['gearbox/gtkwave/inst']
    timekeep.timestep_changed.disconnect(gtkwave.update)
    for b in gtkwave.buffers:
        b.delete()

    reg['gearbox/gtkwave/inst'] = None


class Signals(NamedTuple):
    ready: str
    valid: str


class GtkWave:
    def __init__(self):
        super().__init__()

        timestep_event_register(self.update)

        self.graph_intfs = []
        self.instances = []
        self.buffers = []

        try:
            vcd = reg['VCD']
            vcd.gear = find('/')
            self.create_gtkwave_instance(vcd, PyGearsVCDMap)
        except KeyError:
            pass

        for m in find_cosim_modules():
            if not isinstance(m, SimVerilated):
                continue

            if m.trace_fn is not None:
                self.create_gtkwave_instance(m, VerilatorVCDMap)

    def create_gtkwave_instance(self, vcd_trace_obj, vcd_map_cls):
        if hasattr(vcd_trace_obj, 'shmid'):
            trace_fn = vcd_trace_obj.shmid
        else:
            trace_fn = vcd_trace_obj.trace_fn

        window = GtkWaveWindow(trace_fn)

        if window.window_id is not None:
            self.create_gtkwave_buffer()
        else:
            print(f'Connecting init for {vcd_trace_obj}, {vcd_map_cls}')
            single_shot_connect(
                window.initialized,
                partial(self.create_gtkwave_buffer, window, vcd_trace_obj,
                        vcd_map_cls))

    def create_gtkwave_buffer(self, window, vcd_trace_obj, vcd_map_cls):

        sigs = [s.strip() for s in window.command('list_signals').split('\n')]

        vcd_map = vcd_map_cls(vcd_trace_obj.gear, sigs)
        intf = GtkWaveGraphIntf(vcd_map, window)
        self.graph_intfs.append(intf)

        buffer = GtkWaveBuffer(intf, window, f'gtkwave - {vcd_map.name}')

        self.instances.append(window)
        self.buffers.append(buffer)

    def item_gtkwave_intf(self, item):
        for intf in self.graph_intfs:
            if intf.has_item_wave(item):
                return intf

    def pipe_gtkwave_instance(self, pipe):
        for intf, inst in zip(self.graph_intfs, self.instances):
            if intf.has_item_wave(pipe):
                return inst

    def update_pipe_statuses(self, pipes):
        intfs = {}
        for p in pipes:
            pipe_intf = self.item_gtkwave_intf(p)
            if pipe_intf is None:
                return None

            if pipe_intf not in intfs:
                intfs[pipe_intf] = []

            intfs[pipe_intf].append(p)

        for intf, pipes in intfs.items():
            intf.update_pipes(pipes)

    def show_item(self, item):
        item_intf = self.item_gtkwave_intf(item)
        if item_intf is None:
            raise ItemNotTraced

        return item_intf.show_item(item)

    @inject
    def update(self, timestep=Inject('gearbox/timestep')):
        if timestep is None:
            timestep = 0

        for w in self.graph_intfs:
            w.update(timestep)


class GtkWaveBuffer(Buffer):
    def __init__(self, intf, gtk_window, name):
        self.intf = intf
        self.gtk_window = gtk_window
        super().__init__(gtk_window, name)

    def activate(self):
        super().activate()
        self.gtk_window.activateWindow()

    def deactivate(self):
        super().deactivate()

    def delete(self):
        super().delete()
        self.gtk_window.close()

    @property
    def domain(self):
        return 'gtkwave'


class PipeActivityVisitor(HierYielderBase):
    def __init__(self, vcd_map):
        self.vcd_map = vcd_map

    def PipeModel(self, node):
        if node.view.isVisible():
            yield node

        return True

    def NodeModel(self, node):
        if node.view.collapsed:
            return True

        if node not in self.vcd_map:
            return True

        yield from super().HierNode(node)

        return True


class NodeActivityVisitor(HierVisitorBase):
    def NodeModel(self, node):
        if not node.rtl.hierarchical and node.rtl not in reg['sim/map']:
            node.set_status('done')
        elif (any(p.status == 'active' for p in node.input_ext_pipes)
              and (not any(p.status == 'active' or p.status == 'handshaked'
                             for p in node.output_ext_pipes))):
            node.set_status('stuck')
        else:
            node.set_status('empty')

        if node.view.collapsed:
            return True


def chunk_list(l, size=2048):
    chunks = []
    cur_chunk = []
    cur_len = 0
    for val in l:
        cur_chunk.append(val)
        cur_len += len(val)
        if cur_len > 1024:
            chunks.append(cur_chunk)
            cur_chunk = []
            cur_len = 0

    if cur_chunk:
        chunks.append(cur_chunk)

    return chunks


class GtkWaveGraphIntf(QtCore.QObject):
    vcd_loaded = QtCore.Signal()

    def __init__(self, vcd_map, gtkwave_intf):
        super().__init__()
        self.vcd_map = vcd_map
        self.graph = vcd_map.subgraph
        self.gtkwave_intf = gtkwave_intf
        # dbg_connect(self.gtkwave_intf.response, self.gtkwave_resp)
        self.gtkwave_intf.response.connect(self.gtkwave_resp)
        self.items_on_wave = {}
        self.should_update = False
        self.updating = False
        self.timestep = 0

    def has_item_wave(self, item):
        return item in self.vcd_map

    def show_item(self, item):
        if isinstance(item, PipeModel):
            return self.show_pipe(item)
        elif isinstance(item, NodeModel):
            return self.show_node(item)

    def show_node(self, node):
        try:
            sigs = self.vcd_map[node]
        except KeyError:
            print(f'No signals found for {node.name}')
            return

        for i in range(0, len(sigs), 20):
            s = sigs[i:i + 20]
            self.gtkwave_intf.command(
                [f'gtkwave::addSignalsFromList {{{" ".join(s)}}}'])

        for i in range(0, len(sigs), 20):
            s = sigs[i:i + 20]
            self.gtkwave_intf.command(
                [f'gtkwave::highlightSignalsFromList {{{" ".join(s)}}}'])

        self.gtkwave_intf.command([f'gtkwave::/Edit/Create_Group {node.name}'])

        self.items_on_wave[node] = node.name

        return node.name

    def show_pipe(self, pipe):

        struct_sigs = collections.defaultdict(dict)

        intf_name = pipe.name.replace('.', '/')
        status_sig = intf_name + '_state'
        try:
            valid_sig, ready_sig = self.vcd_map.pipe_handshake_signals(pipe)
        except KeyError:
            print(f'No signals found for {pipe.name}')
            return

        self.items_on_wave[pipe] = intf_name

        commands = []

        dti_translate_path = os.path.join(os.path.dirname(__file__),
                                          "dti_translate.py")
        commands.append(
            f'gtkwave::addSignalsFromList {{{valid_sig} {ready_sig}}}')
        commands.append(
            f'gtkwave::highlightSignalsFromList {{{valid_sig} {ready_sig}}}')

        commands.append(f'gtkwave::/Edit/Combine_Down {{{status_sig}}}')
        commands.append(f'select_trace_by_name {{{status_sig}}}')
        commands.append('gtkwave::/Edit/Toggle_Group_Open|Close')
        commands.append(
            f'gtkwave::setCurrentTranslateTransProc "{sys.executable} {dti_translate_path}"'
        )
        commands.append(f'gtkwave::installTransFilter 1')

        def dfs(name, lvl):
            if isinstance(lvl, dict):
                selected = []
                for k, v in lvl.items():
                    if isinstance(v, dict):
                        ret = yield from dfs(k, v)
                        selected.extend(ret)
                    else:
                        selected.extend(v)

            else:
                selected = lvl

            yield name, selected
            return selected

        struct_sigs = self.vcd_map.get_pipe_groups(pipe)

        groups = list(dfs(intf_name, struct_sigs))

        all_sigs = groups[-1][1]

        for c in chunk_list(all_sigs):
            commands.append('gtkwave::addSignalsFromList {' + " ".join(c) + '}')

        for name, selected in reversed(groups):

            for c in chunk_list(selected):
                commands.append('gtkwave::highlightSignalsFromList {' + " ".join(c) + '}')

            commands.append(f'gtkwave::/Edit/Combine_Down {name}')

        commands.append('select_trace_by_name {' + intf_name + '}')
        commands.append('gtkwave::/Edit/Toggle_Group_Open|Close')

        self.gtkwave_intf.command(commands)

        return intf_name

    def update_rtl_intf(self, pipe, wave_status):
        done = get_source_producer(pipe.rtl).done

        if wave_status == '1 0':
            status = 'active'
        elif wave_status == '0 1':
            status = 'waited'
        elif wave_status == '1 1':
            status = 'handshaked'
        elif done:
            status = 'done'
        else:
            status = 'empty'

        pipe.set_status(status)

    @property
    def cmd_id(self):
        return id(self) & 0xffff

    def gtkwave_resp(self, ret, cmd_id):
        if cmd_id != self.cmd_id:
            return

        if self.gtkwave_intf.shmidcat:
            ts = timestep()
            if ts is None:
                ts = 0

            status, _, gtk_timestep = ret.rpartition('\n')
            if gtk_timestep:
                try:
                    self.timestep = (int(gtk_timestep) // 10) - 1
                except ValueError:
                    self.timestep = 0

            if not gtk_timestep or ts - self.timestep > 100:
                self.should_update = False
                self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
                # print("Again")
                return

        self.update_pipes(
            PipeActivityVisitor(self.vcd_map).visit(self.vcd_map.model))
        # self.update_pipes(p for p in self.vcd_map.vcd_pipes if p.view.isVisible())

        if self.gtkwave_intf.shmidcat:
            self.gtkwave_intf.command(
                f'set_marker_if_needed {self.timestep*10}')

        if self.should_update:
            self.should_update = False
            # print(f'Updating immediatelly')
            if self.gtkwave_intf.shmidcat:
                self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
            else:
                self.gtkwave_intf.command_nb(f'gtkwave::reLoadFile',
                                             self.cmd_id)

        else:
            self.updating = False

        # print(f'Exiting')

    def update_pipes(self, pipes):

        ts = self.vcd_map.timestep

        signal_names = [(pipe, self.vcd_map.pipe_data_signal_stem(pipe)[:-4])
                        for pipe in pipes if pipe.status[0] != ts]

        for i in range(0, len(signal_names), 20):

            cur_slice = slice(i, min(len(signal_names), i + 20))
            cur_names = signal_names[cur_slice]

            ret = self.gtkwave_intf.command(
                f'get_values {ts*10} [list {" ".join(s[1] for s in cur_names)}]'
            )

            if ret is None:
                return

            rtl_status = ret.split('\n')

            if len(rtl_status) != (cur_slice.stop - cur_slice.start):
                continue

            for wave_status, (pipe, _) in zip(rtl_status, cur_names):
                self.update_rtl_intf(pipe, wave_status.strip())

        NodeActivityVisitor().visit(reg['gearbox/graph_model'])

    @inject
    def update(self, timestep=Inject('gearbox/timestep')):
        if timestep is None:
            timestep = 0

        # print(
        #     f"Updating {self.vcd_map.name} from {self.timestep} to {timestep}, id: {self.cmd_id}"
        # )

        if timestep < self.timestep:
            self.update_pipes(
                PipeActivityVisitor(self.vcd_map).visit(self.vcd_map.model))
            # self.update_pipes(p for p in self.vcd_map.vcd_pipes if p.view.isVisible())
            self.gtkwave_intf.command(f'set_marker_if_needed {timestep*10}')
        elif not self.updating:
            self.should_update = False
            self.updating = True
            if self.gtkwave_intf.shmidcat:
                self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
            else:
                self.gtkwave_intf.command_nb(f'gtkwave::reLoadFile',
                                             self.cmd_id)
        else:
            self.should_update = True

    def close(self):
        self.gtkwave_intf.close()


class GtkWaveBufferPlugin(LayoutPlugin):
    @classmethod
    def bind(cls):
        reg['gearbox/plugins/gtkwave'] = {}

        @inject
        def menu_visibility(var,
                            visible,
                            gtkwave=MayInject('gearbox/gtkwave/inst')):
            if gtkwave:
                for inst in gtkwave.instances:
                    inst.command('gtkwave::toggleStripGUI')

        reg.confdef('gearbox/gtkwave/menus',
                    default=False,
                    setter=menu_visibility)
