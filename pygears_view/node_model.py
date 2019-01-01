from pygears.core.hier_node import NamedHierNode
from .node import NodeItem, hier_expand, hier_painter, node_painter
from pygears.core.port import InPort

from .constants import Z_VAL_PIPE


class NodeModel(NamedHierNode):
    def __init__(self, gear, parent=None):
        super().__init__(parent=parent)

        self.gear = gear
        self.view = NodeItem(
            gear.basename,
            parent=(None if parent is None else parent.view),
            model=self)

        if parent is not None:
            parent.view.add_node(self.view)
            for port in self.gear.in_ports + self.gear.out_ports:
                self.view._add_port(port)

        for child in self.gear.child:
            n = NodeModel(child, self)
            if parent is not None:
                n.view.hide()

        self.setup_view()

    @property
    def name(self):
        return self.gear.name

    @property
    def basename(self):
        return self.gear.basename

    @property
    def hierarchical(self):
        return bool(self.gear.child)

    def setup_view(self):

        view = self.view

        if self.parent is not None:
            if self.hierarchical:
                view.setZValue(Z_VAL_PIPE - 1)
                view.size_expander = hier_expand
                view.painter = hier_painter
            else:
                view.size_expander = lambda x: None
                view.painter = node_painter

        view.setup_done()

        for graph_node in self.child:
            child = graph_node.gear

            if child.child:
                graph_node.view.collapse()

            for port in child.in_ports:
                producer = port.producer.producer

                if producer.gear is self.gear:
                    src_port = self.view.inputs[producer.index]
                    dest_port = graph_node.view.inputs[port.index]
                    self.view.connect(src_port, dest_port)

            for port in child.out_ports:
                for consumer in port.consumer.consumers:

                    if consumer.gear is self.gear:
                        consumer_graph_node = self.view
                    else:
                        consumer_graph_node = self[consumer.gear.basename].view

                    if consumer_graph_node:
                        src_port = graph_node.view.outputs[port.index]

                        if isinstance(consumer, InPort):
                            dest_port = consumer_graph_node.inputs[consumer.
                                                                   index]
                        else:
                            dest_port = consumer_graph_node.outputs[consumer.
                                                                    index]

                        self.view.connect(src_port, dest_port)
