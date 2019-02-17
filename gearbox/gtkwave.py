from PySide2 import QtCore
import collections

from .timekeep import timestep, timestep_event_register, max_timestep
from pygears.sim.modules import SimVerilated
from .node_model import find_cosim_modules, PipeModel, NodeModel
from pygears.core.hier_node import HierVisitorBase
from pygears.conf import Inject, MayInject, bind, reg_inject, registry
from typing import NamedTuple
from .gtkwave_intf import GtkWaveWindow
from .layout import active_buffer, Buffer
import fnmatch
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
        self.item_signals = {}
        self.pipe_to_port_map = {}

    @property
    @reg_inject
    def subgraph(self, graph=Inject('gearbox/graph_model')):
        return graph

    @property
    def name(self):
        return "Main"

    @property
    def vcd_fn(self):
        return self.vcd.trace_fn

    def pipe_data_signal_stem(self, item):
        return self.item_name_stem(item) + '.data'

    def pipe_handshake_signals(self, item):
        return (self.item_name_stem(item) + '.valid',
                self.item_name_stem(item) + '.ready')

    def item_basename(self, item):
        item_name_stem = item.name[1:]
        return item_name_stem.replace('/', '.')

    def item_name_stem(self, item):
        port = self.pipe_to_port_map[item]
        return self.item_basename(port)

    def get_signals_for_item(self, item):
        if item not in self.item_signals:
            if not hasattr(self, 'signal_list'):
                self.signal_list = [
                    s.strip() for s in self.gtkwave_intf.command(
                        'list_signals').split('\n')
                ]

            if isinstance(item, NodeModel):
                self.item_signals[item] = []
            elif isinstance(item, PipeModel):
                producer_port = item.rtl.producer
                self.item_signals[item] = []
                try:
                    while (not self.item_signals[item] and producer_port):
                        self.pipe_to_port_map[item] = producer_port
                        match = self.item_basename(producer_port) + '.*'
                        self.item_signals[item] = fnmatch.filter(
                            self.signal_list, match)

                        # Try to find next producer port in chain
                        producer_port = producer_port.producer.producer

                except AttributeError:
                    pass

        return self.item_signals[item]


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
        self.item_signals = {}
        self.signal_name_map = {}

    @property
    @reg_inject
    def subgraph(self, graph=Inject('gearbox/graph_model')):
        return graph[self.sim_module.gear.name[1:]]

    def pipe_data_signal_stem(self, item):
        return self.item_name_stem(item) + '_data'

    def pipe_handshake_signals(self, item):
        return (self.item_name_stem(item) + '_valid',
                self.item_name_stem(item) + '_ready')

    def item_basename(self, item):
        item_name_stem = item.name[len(self.rtl_node.parent.name) + 1:]
        return item_name_stem.replace('/', '.')

    def item_name_stem(self, item):
        return '.'.join((self.path_prefix, self.item_basename(item)))

    @property
    def name(self):
        return self.sim_module.name

    @property
    def vcd_fn(self):
        return self.sim_module.trace_fn

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

    def get_signals_for_item(self, item):
        if item in self.item_signals:
            return self.item_signals[item]

        if not self.signal_name_map:
            self.signal_name_map = self.make_relative_signal_name_map(
                self.path_prefix, self.gtkwave_intf.command('list_signals'))

        if not self.rtl_node.is_descendent(item.rtl):
            return

        if isinstance(item, PipeModel):
            match = self.item_basename(item) + '_*'
        elif isinstance(item, NodeModel):
            match = self.item_basename(item) + '.*'

        signals = fnmatch.filter(self.signal_name_map.keys(), match)
        return [self.signal_name_map[s] for s in signals]


@reg_inject
def gtkwave(sim_bridge=Inject('gearbox/sim_bridge')):
    sim_bridge.sim_started.connect(gtkwave_create)


def gtkwave_create():
    bind('gearbox/gtkwave', GtkWave())


class Signals(NamedTuple):
    ready: str
    valid: str


class GraphItemCollector(HierVisitorBase):
    def __init__(self, vcd_map):
        self.vcd_pipes = {}
        self.vcd_nodes = {}
        self.vcd_map = vcd_map

    def PipeModel(self, pipe):
        if pipe not in self.vcd_pipes:
            self.vcd_pipes[pipe] = self.vcd_map.get_signals_for_item(pipe)

    def NodeModel(self, node):
        if not node.rtl.is_hierarchical:
            if node not in self.vcd_nodes:
                self.vcd_nodes[node] = self.vcd_map.get_signals_for_item(node)


class PyGearsGraphItemCollector(GraphItemCollector):
    def NodeModel(self, node):
        if ('sim_cls' in node.rtl.params
                and node.rtl.params['sim_cls'] is not None):
            return True
        else:
            super().NodeModel(node)


class GtkWave:
    def __init__(self):
        super().__init__()

        timestep_event_register(self.update)

        self.graph_intfs = []
        self.instances = []
        self.buffers = []

        try:
            self.create_gtkwave_instance(
                registry('VCD'), PyGearsVCDMap, PyGearsGraphItemCollector)
        except KeyError:
            pass

        for m in find_cosim_modules():
            if not isinstance(m, SimVerilated):
                continue

            if m.trace_fn is not None:
                self.create_gtkwave_instance(m, VerilatorVCDMap,
                                             GraphItemCollector)

    def create_gtkwave_instance(self, vcd_trace_obj, vcd_map_cls,
                                graph_item_collector_cls):
        if hasattr(vcd_trace_obj, 'shmid'):
            trace_fn = vcd_trace_obj.shmid
        else:
            trace_fn = vcd_trace_obj.trace_fn

        instance = GtkWaveWindow(trace_fn)
        vcd_map = vcd_map_cls(vcd_trace_obj, instance)
        intf = GtkWaveGraphIntf(vcd_map, instance,
                                graph_item_collector_cls(vcd_map))

        buffer = GtkWaveBuffer(intf, instance, f'gtkwave - {vcd_map.name}')

        self.graph_intfs.append(intf)
        self.instances.append(instance)
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

    @reg_inject
    def update(self, timestep=Inject('gearbox/timestep')):
        if timestep is None:
            timestep = 0

        for w in self.graph_intfs:
            w.update(timestep)


class GtkWaveBuffer(Buffer):
    def __init__(self, intf, instance, name):
        self.intf = intf
        self.name = name
        self.instance = instance
        self.instance.initialized.connect(self.load)
        self.window = None

    @reg_inject
    def load(self, main=Inject('gearbox/main')):
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

    def __init__(self, vcd_map, gtkwave_intf, graph_item_collector):
        super().__init__()
        self.vcd_map = vcd_map
        self.graph = vcd_map.subgraph
        self.gtkwave_intf = gtkwave_intf
        self.loaded = False
        self.item_collect = graph_item_collector
        self.items_on_wave = {}
        self.should_update = False
        self.updating = False
        gtkwave_intf.initialized.connect(self.update)

    def has_item_wave(self, item):
        if isinstance(item, PipeModel):
            return item in self.item_collect.vcd_pipes
        elif isinstance(item, NodeModel):
            return item in self.item_collect.vcd_nodes

    def show_item(self, item):

        if isinstance(item, PipeModel):
            return self.show_pipe(item)
        elif isinstance(item, NodeModel):
            return self.show_node(item)

    def show_node(self, node):
        sigs = self.vcd_map.get_signals_for_item(node)
        commands = []
        commands.append(f'gtkwave::addSignalsFromList {{{" ".join(sigs)}}}')
        commands.append(
            f'gtkwave::highlightSignalsFromList {{{" ".join(sigs)}}}')

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

        for s in self.vcd_map.get_signals_for_item(pipe):
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

        groups = list(dfs(intf_name, struct_sigs['data']))
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

        if self.gtkwave_intf.shmidcat:
            ts = timestep()
            if ts is None:
                ts = 0

            status, _, ret = ret.rpartition('\n')
            # print(status)
            self.timestep = (int(ret) // 10) - 1
            self.gtkwave_intf.response.disconnect(self.gtkwave_resp)

            # print(f"Updated: {ts} <-> {self.timestep}")
            if ts - self.timestep > 1000:
                self.should_update = False
                self.gtkwave_intf.response.connect(self.gtkwave_resp)
                self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
                # print("Again")
                return

        self.update_pipes(
            p for p in self.item_collect.vcd_pipes if p.view.isVisible())

        if self.gtkwave_intf.shmidcat:
            self.gtkwave_intf.command(
                f'set_marker_if_needed {self.timestep*10}')

        if self.should_update:
            self.should_update = False
            self.gtkwave_intf.response.connect(self.gtkwave_resp)
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
        ts = timestep()
        if ts is None:
            ts = 0

        signal_names = [(pipe, self.vcd_map.pipe_data_signal_stem(pipe)[:-4])
                        for pipe in pipes if pipe.status[0] != ts]

        for i in range(0, len(signal_names), 20):

            cur_slice = slice(i, min(len(signal_names), i + 20))
            cur_names = signal_names[cur_slice]

            ret = self.gtkwave_intf.command(
                f'get_values {ts*10} [list {" ".join(s[1] for s in cur_names)}]'
            )
            rtl_status = ret.split('\n')

            # assert len(rtl_status) == (cur_slice.stop - cur_slice.start)
            if len(rtl_status) != (cur_slice.stop - cur_slice.start):
                continue

            for wave_status, (pipe, _) in zip(rtl_status, cur_names):
                self.update_rtl_intf(pipe, wave_status.strip())

        NodeActivityVisitor().visit(registry('gearbox/graph_model'))

    @reg_inject
    def update(self, timestep=Inject('gearbox/timestep')):
        if not self.loaded:
            # ret = self.gtkwave_intf.command(
            #     f'gtkwave::loadFile {self.vcd_map.vcd_fn}')

            # if "File load failure" in ret:
            #     return False

            self.timestep = 0
            self.item_collect.visit(self.graph)
            self.loaded = True
            self.vcd_loaded.emit()

        # mts = max_timestep()
        # if mts is None:
        #     mts = 0

        if timestep is None:
            timestep = 0

        # print(f"Updating pipes {timestep} <-> {self.timestep}: {self.cmd_id}")

        if timestep < self.timestep:
            self.update_pipes(
                p for p in self.item_collect.vcd_pipes if p.view.isVisible())
            self.gtkwave_intf.command(f'set_marker_if_needed {timestep*10}')
        elif not self.updating:
            self.should_update = False
            self.updating = True
            self.gtkwave_intf.response.connect(self.gtkwave_resp)
            if self.gtkwave_intf.shmidcat:
                self.gtkwave_intf.command_nb(f'gtkwave::nop', self.cmd_id)
            else:
                self.gtkwave_intf.command_nb(f'gtkwave::reLoadFile',
                                             self.cmd_id)
        else:
            self.should_update = True
