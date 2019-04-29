from .graph import GraphVisitor
from pygears.conf import Inject, inject
from pygears.rtl.gear import gear_from_rtl_port


class GraphPipeCollector(GraphVisitor):
    @inject
    def __init__(self, sim_activity=Inject('sim/activity')):
        self.sim_activity = sim_activity
        self.py_intfs = set()

    def pipe(self, pipe):
        if pipe not in self.py_intfs:
            try:
                port = pipe.model.intf.producer
                self.sim_activity.get_port_status(gear_from_rtl_port(port))
                self.py_intfs.add(pipe)
                return
            except:
                pass


class GraphSimStatus:
    def __init__(self, graph=Inject('gearbox/graph')):
        self.graph = graph
        self.pipe_collect = GraphPipeCollector()
        self.pipe_collect.visit(self.graph.top)
        self.py_intfs = self.pipe_collect.py_intfs

    @inject
    def update(self, sim_activity=Inject('sim/activity')):
        for py_intf in self.py_intfs:
            py_intf.set_status(sim_activity.get_port_status(py_intf.model))
