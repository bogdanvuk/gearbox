from pygears.conf import Inject, reg_inject
from pygears.rtl.gear import rtl_from_gear_port
from pygears_view.gtkwave import verilator_waves
from typing import NamedTuple


class GraphVisitor:
    def visit(self, node):
        self.node(node)

    def node(self, node):
        for pipe in node.pipes:
            self.pipe(pipe)

        for node in node._nodes:
            self.node(node)

    def pipe(self):
        pass


class Signals(NamedTuple):
    ready: str
    valid: str


class GraphPipeCollector(GraphVisitor):
    @reg_inject
    def __init__(self, sim_activity=Inject('sim/activity')):
        self.sim_activity = sim_activity
        self.py_intfs = set()
        self.rtl_intfs = {}

    def pipe(self, pipe):
        if (pipe not in self.py_intfs) and (pipe not in self.rtl_intfs):
            try:
                self.sim_activity.get_port_status(pipe.model)
                self.py_intfs.add(pipe)
                return
            except:
                pass

            port = pipe.output_port.model
            rtl_port = rtl_from_gear_port(port)
            if rtl_port is None:
                return

            rtl_intf = rtl_port.consumer
            if rtl_intf is None:
                return

            try:
                all_sigs = verilator_waves[0].get_signals_for_intf(rtl_intf)
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


class GraphSimStatus:
    def __init__(self, graph):
        self.graph = graph
        self.pipe_collect = GraphPipeCollector()

    @reg_inject
    def update_py_intf(self, pipe, sim_activity=Inject('sim/activity')):
        pipe.set_status(sim_activity.get_port_status(pipe.model))

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
        print("Updating")
        self.pipe_collect.visit(self.graph.top)
        for py_intf in self.pipe_collect.py_intfs:
            self.update_py_intf(py_intf)

        signal_names = list(self.pipe_collect.rtl_intfs.values())

        # print(signal_names)
        ret = gtkwave.command(f'get_values [list {" ".join(signal_names)}]')
        # print(ret)
        self.rtl_status = ret.split('\n')

        # assert len(self.rtl_status) == len(self.pipe_collect.rtl_intfs)
        if len(self.rtl_status) != len(self.pipe_collect.rtl_intfs):
            return

        for wave_status, rtl_intf in zip(self.rtl_status,
                                         self.pipe_collect.rtl_intfs):
            self.update_rtl_intf(rtl_intf, wave_status.strip())
