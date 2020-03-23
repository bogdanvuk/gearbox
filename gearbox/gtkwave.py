from PySide2 import QtCore
import collections
import sys

from pygears.core.gear import Gear
from .timekeep import timestep, timestep_event_register
from pygears.sim.modules import SimVerilated
from .node_model import find_cosim_modules, PipeModel, NodeModel
from pygears.core.hier_node import HierVisitorBase
from pygears.conf import Inject, MayInject, inject, reg
from typing import NamedTuple
from .gtkwave_intf import GtkWaveWindow
from .layout import active_buffer, Buffer, LayoutPlugin
from .utils import single_shot_connect
from .dbg import dbg_connect
from functools import partial
import os
import re


class ItemNotTraced(Exception):
    pass


def active_intf():
    active_buffer()


class PyGearsVCDMap:
    def __init__(
        self,
        vcd,
        gtkwave_intf,
    ):
        self.gtkwave_intf = gtkwave_intf
        self.vcd = vcd

        self.signal_name_map = {
            s.strip(): s.strip()
            for s in self.gtkwave_intf.command('list_signals').split('\n')
        }

        self.item_signals, self.pipe_to_port_map = get_pg_vcd_item_signals(
            self.subgraph, self.signal_name_map)

        # self.pipe_to_port_map = {}

    @property
    @inject
    def subgraph(self, graph=Inject('gearbox/graph_model')):
        return graph

    @property
    def name(self):
        return "Main"

    @property
    def timestep(self):
        ts = timestep()
        if ts is None:
            return 0

        return ts

    @property
    def vcd_fn(self):
        return self.vcd.trace_fn

    def pipe_data_signal_stem(self, item):
        return self.item_name_stem(item) + '.data'

    def pipe_handshake_signals(self, item):
        return (
            self.item_name_stem(item) + '.valid', self.item_name_stem(item) + '.ready')

    def item_basename(self, item):
        item_name_stem = item.name[1:]
        return item_name_stem.replace('/', '.')

    def item_name_stem(self, item):
        port = self.pipe_to_port_map[item]
        # return self.item_basename(item)
        return self.item_basename(port)

    @property
    def vcd_pipes(self):
        for item in self.item_signals:
            if isinstance(item, PipeModel):
                yield item

    @property
    def vcd_nodes(self):
        for item in self.item_signals:
            if isinstance(item, NodeModel):
                yield item

    def __contains__(self, item):
        return item in self.item_signals

    def __getitem__(self, item):
        return self.item_signals[item]


def get_pg_vcd_item_signals(subgraph, signal_name_map):
    item_signals = {}
    pipe_to_port_map = {}
    item = subgraph.rtl
    item_path = []

    for name, s in signal_name_map.items():
        # item = subgraph
        item = subgraph.rtl
        path = name.split('.')

        new_item_path = []

        import itertools
        for p, prev_item in itertools.zip_longest(path, item_path):
            if prev_item and p == prev_item.basename:
                item = prev_item
            else:
                try:
                    item = item[p]
                except KeyError:
                    break

            new_item_path.append(item)

            if not item.hierarchical:
                break

        item_path = new_item_path

        def port_by_name(item, port_name):
            def _port_by_name(ports, name):
                for port in ports:
                    if port.basename == name:
                        return port
                else:
                    raise KeyError

            port = None

            try:
                port = _port_by_name(item.in_ports, port_name)
            except KeyError:
                pass

            try:
                port = _port_by_name(item.out_ports, port_name)
            except KeyError:
                pass

            return port

        if isinstance(item, Gear):
            port_name = path[len(new_item_path)]
            port = port_by_name(item, port_name)

            if port is not None:
                # rtl_port = closest_rtl_from_gear_port(port)
                rtl_port = port

                try:
                    out_intf = rtl_port.consumer
                    pipe = subgraph[out_intf.name]
                    pipe_to_port_map[pipe] = port
                    item = pipe
                except (KeyError, AttributeError):
                    try:
                        in_intf = rtl_port.producer
                        if in_intf.is_broadcast:
                            index = in_intf.consumers.index(rtl_port)
                            pipe = subgraph[f'{in_intf.name}_bc_{index}']
                        else:
                            pipe = subgraph[in_intf.name]

                        pipe_to_port_map[pipe] = port
                        item = pipe
                    except (KeyError, AttributeError):
                        pass

        if item not in item_signals:
            item_signals[item] = []

        item_signals[item].append(s)

    return item_signals, pipe_to_port_map


def get_verilator_item_signals(subgraph, signal_name_map):
    item_signals = {}
    item = subgraph
    item_path = []

    def find_child(parent, name):
        # Try name as submodule
        if name in parent:
            return parent[name]

        # Try name as interface name
        intf_name = p.rpartition('_')[0]

        if intf_name in parent:
            return parent[intf_name]

        return None

    for name, s in signal_name_map.items():
        item = subgraph
        path = name.split('.')

        new_item_path = []

        import itertools
        for p, prev_item in itertools.zip_longest(path[1:], item_path):
            if prev_item and p == prev_item.basename:
                item = prev_item
            else:
                child_item = find_child(item, p)
                if child_item is None:
                    break

                item = child_item

            new_item_path.append(item)

            if not item.hierarchical:
                break

        item_path = new_item_path

        if item not in item_signals:
            item_signals[item] = []

        item_signals[item].append(s)

    return item_signals


class VerilatorVCDMap:
    @inject
    def __init__(self, sim_module, gtkwave_intf):
        self.gtkwave_intf = gtkwave_intf
        self.sim_module = sim_module

        # self.rtl_node = rtl_map[self.sim_module.gear]
        self.rtl_node = self.sim_module.gear
        if self.sim_module.lang == 'sv':
            hdlmod = reg[f'hdlgen/map'][sim_module.top]
            self.path_prefix = '.'.join(['TOP', f'{hdlmod.module_name}_v_wrap'])
        else:
            self.path_prefix = 'TOP'

        self.signal_name_map = self.make_relative_signal_name_map(
            self.path_prefix, self.gtkwave_intf.command('list_signals'))

        self.item_signals = get_verilator_item_signals(
            self.subgraph, self.signal_name_map)

        print("VCD Init done")

    @property
    @inject
    def subgraph(self, graph=Inject('gearbox/graph_model')):
        return graph[self.sim_module.gear.name[1:]]

    def pipe_data_signal_stem(self, item):
        return self.item_name_stem(item) + '_data'

    def pipe_handshake_signals(self, item):
        return (
            self.item_name_stem(item) + '_valid', self.item_name_stem(item) + '_ready')

    @property
    def vcd_pipes(self):
        for item in self.item_signals:
            if isinstance(item, PipeModel):
                yield item

    def vcd_nodes(self):
        for item in self.item_signals:
            if isinstance(item, NodeModel):
                yield item

    def item_basename(self, item):
        parent = item.rtl.parent
        path = [item.basename]
        while parent != self.rtl_node.parent:
            path.append(reg['hdlgen/map'][parent].inst_name)
            parent = parent.parent

        return '.'.join(reversed(path))

        # item_name_stem = item.name[len(self.rtl_node.parent.name) + 1:]
        # return item_name_stem.replace('/', '.')

    def item_name_stem(self, item):
        return '.'.join((self.path_prefix, self.item_basename(item)))

    @property
    def name(self):
        return self.sim_module.name

    @property
    def timestep(self):
        ts = timestep()
        if ts is None:
            return 0

        return ts

    @property
    def vcd_fn(self):
        return self.sim_module.trace_fn

    def make_relative_signal_name_map(self, path_prefix, signal_list):
        signal_name_map = {}
        for sig_name in signal_list.split('\n'):
            sig_name = sig_name.strip()

            basename = re.search(
                r"{0}\.({1}\..*)".format(
                    path_prefix, reg['hdlgen/map'][self.sim_module.top].inst_name),
                sig_name)

            if basename:
                signal_name_map[basename.group(1)] = sig_name

        return signal_name_map

    def __contains__(self, item):
        return item in self.item_signals

    def __getitem__(self, item):
        return self.item_signals[item]


@inject
def gtkwave(graph_model_ctrl=Inject('gearbox/graph_model_ctrl')):
    dbg_connect(graph_model_ctrl.working_model_loaded, gtkwave_create)


@inject
def gtkwave_create(sim_bridge=Inject('gearbox/sim_bridge')):
    gtkwave = GtkWave()
    reg['gearbox/gtkwave/inst'] = gtkwave
    single_shot_connect(sim_bridge.model_closed, gktwave_delete)


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
            self.create_gtkwave_instance(reg['VCD'], PyGearsVCDMap)
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
            dbg_connect(
                window.initialized,
                partial(self.create_gtkwave_buffer, window, vcd_trace_obj, vcd_map_cls))

    def create_gtkwave_buffer(self, window, vcd_trace_obj, vcd_map_cls):
        vcd_map = vcd_map_cls(vcd_trace_obj, window)
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
        super().__init__(gtk_window.widget, name)

    def activate(self):
        super().activate()
        self.gtk_window.widget.activateWindow()

    def deactivate(self):
        super().deactivate()

    def delete(self):
        super().delete()
        self.gtk_window.close()

    @property
    def domain(self):
        return 'gtkwave'


class NodeActivityVisitor(HierVisitorBase):
    def NodeModel(self, node):
        if (any(p.status == 'active' for p in node.input_ext_pipes)
                and (not any(p.status == 'active' or p.status == 'handshaked'
                             for p in node.output_ext_pipes))):
            node.set_status('stuck')
        else:
            node.set_status('empty')


class GtkWaveGraphIntf(QtCore.QObject):
    vcd_loaded = QtCore.Signal()

    def __init__(self, vcd_map, gtkwave_intf):
        super().__init__()
        self.vcd_map = vcd_map
        self.graph = vcd_map.subgraph
        self.gtkwave_intf = gtkwave_intf
        dbg_connect(self.gtkwave_intf.response, self.gtkwave_resp)
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
        sigs = self.vcd_map[node]
        commands = []
        commands.append(f'gtkwave::addSignalsFromList {{{" ".join(sigs)}}}')
        commands.append(f'gtkwave::highlightSignalsFromList {{{" ".join(sigs)}}}')

        commands.append(f'gtkwave::/Edit/Create_Group {node.name}')

        self.gtkwave_intf.command(commands)

        self.items_on_wave[node] = node.name

        return node.name

    def show_pipe(self, pipe):

        struct_sigs = collections.defaultdict(dict)
        sig_names = []

        intf_name = pipe.name.replace('.', '/')
        status_sig = intf_name + '_state'
        valid_sig, ready_sig = self.vcd_map.pipe_handshake_signals(pipe)
        data_sig_stem = self.vcd_map.pipe_data_signal_stem(pipe)
        self.items_on_wave[pipe] = intf_name

        commands = []

        dti_translate_path = os.path.join(os.path.dirname(__file__), "dti_translate.py")
        commands.append(f'gtkwave::addSignalsFromList {{{valid_sig} {ready_sig}}}')
        commands.append(f'gtkwave::highlightSignalsFromList {{{valid_sig} {ready_sig}}}')

        commands.append(f'gtkwave::/Edit/Combine_Down {{{status_sig}}}')
        commands.append(f'select_trace_by_name {{{status_sig}}}')
        commands.append('gtkwave::/Edit/Toggle_Group_Open|Close')
        commands.append(
            f'gtkwave::setCurrentTranslateTransProc "{sys.executable} {dti_translate_path}"')
        commands.append(f'gtkwave::installTransFilter 1')

        for s in self.vcd_map[pipe]:
            if s.startswith(data_sig_stem):
                sig_names.append(s)

                stem = s[len(data_sig_stem) - 4:]
                sig_name_no_width = stem.partition('[')[0]

                path = sig_name_no_width.split('.')
                place = struct_sigs
                for p in path[:-1]:
                    if p not in place:
                        place[p] = {}

                    place = place[p]

                place[path[-1]] = s

        commands.append('gtkwave::addSignalsFromList {' + " ".join(sig_names) + '}')

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

        groups = list(dfs(intf_name, struct_sigs['data']))
        for name, selected in reversed(groups):
            commands.append(
                'gtkwave::highlightSignalsFromList {' + " ".join(selected) + '}')
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

        self.update_pipes(p for p in self.vcd_map.vcd_pipes if p.view.isVisible())

        if self.gtkwave_intf.shmidcat:
            self.gtkwave_intf.command(f'set_marker_if_needed {self.timestep*10}')

        if self.should_update:
            self.should_update = False
            # print(f'Updating immediatelly')
            if self.gtkwave_intf.shmidcat:
                self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
            else:
                self.gtkwave_intf.command_nb(f'gtkwave::reLoadFile', self.cmd_id)

        else:
            self.updating = False

        # print(f'Exiting')

    def update_pipes(self, pipes):
        ts = self.vcd_map.timestep

        signal_names = [
            (pipe, self.vcd_map.pipe_data_signal_stem(pipe)[:-4]) for pipe in pipes
            if pipe.status[0] != ts
        ]

        for i in range(0, len(signal_names), 20):

            cur_slice = slice(i, min(len(signal_names), i + 20))
            cur_names = signal_names[cur_slice]

            ret = self.gtkwave_intf.command(
                f'get_values {ts*10} [list {" ".join(s[1] for s in cur_names)}]')
            rtl_status = ret.split('\n')

            # assert len(rtl_status) == (cur_slice.stop - cur_slice.start)
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
            self.update_pipes(p for p in self.vcd_map.vcd_pipes if p.view.isVisible())
            self.gtkwave_intf.command(f'set_marker_if_needed {timestep*10}')
        elif not self.updating:
            self.should_update = False
            self.updating = True
            if self.gtkwave_intf.shmidcat:
                self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
            else:
                self.gtkwave_intf.command_nb(f'gtkwave::reLoadFile', self.cmd_id)
        else:
            self.should_update = True


class GtkWaveBufferPlugin(LayoutPlugin):
    @classmethod
    def bind(cls):
        reg['gearbox/plugins/gtkwave'] = {}

        @inject
        def menu_visibility(var, visible, gtkwave=MayInject('gearbox/gtkwave/inst')):
            if gtkwave:
                for inst in gtkwave.instances:
                    inst.command('gtkwave::toggleStripGUI')

        reg.confdef('gearbox/gtkwave/menus', default=False, setter=menu_visibility)
