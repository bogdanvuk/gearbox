#!/usr/bin/python
import sys

from PySide2 import QtWidgets

from NodeGraphQt import NodeGraph, Node, Backdrop
from pygears import bind
from pygears.core.gear import InPort
from pygears.conf.log import INFO
from pygears.common import add, shred
from pygears.util.print_hier import print_hier
from pygears.core.hier_node import HierVisitorBase
from NodeGraphQt.base.commands import NodeAddedCmd
from pygears.conf import Inject, reg_inject

# import example nodes from the "example_nodes" package

gear_graph_node_map = {}
graph_node_gear_map = {}


def inst_children(node):
    child_node_map = {}

    for child in node.gear.child:

        if not child.child:
            graph_node = NodeGear(child, node)
        else:
            graph_node = HierGear(child, node)

        child_node_map[child] = graph_node

    for child, graph_node in child_node_map.items():
        child = graph_node.gear

        if child.child:
            graph_node.collapse()

        for port in child.in_ports:
            producer = port.producer.producer

            if producer.gear is node.gear:
                src_port = node.input(producer.index)
                dest_port = graph_node.input(port.index)
                node.connect(src_port, dest_port)

        for port in child.out_ports:
            for consumer in port.consumer.consumers:

                if consumer.gear is node.gear:
                    consumer_graph_node = node
                else:
                    consumer_graph_node = child_node_map.get(consumer.gear)

                if consumer_graph_node:
                    if isinstance(consumer, InPort):
                        src_port = graph_node.output(port.index)
                        dest_port = consumer_graph_node.input(consumer.index)
                    else:
                        src_port = consumer_graph_node.output(consumer.index)
                        dest_port = graph_node.output(port.index)

                    node.connect(src_port, dest_port)

    return child_node_map


class Top:
    def __init__(self, gear, graph):
        self.parent = None
        self._graph = graph
        self.gear = gear
        self.child_node_map = inst_children(self)

    @property
    def graph(self):
        return self._graph

    def add_node(self, node):
        self._graph.add_node(node)

    def connect(self, port1, port2):
        self._graph.connect(port1, port2)

    def layout(self):
        self._graph.layout()


class HierGear(Backdrop):
    """
    This is a example test node.
    """

    # set a unique node identifier.
    __identifier__ = 'com.chantasticvfx'

    # set the initial default node name.
    NODE_NAME = 'My Node'

    def __hash__(self):
        return id(self)

    def __init__(self, gear, parent=None):
        super().__init__()
        self.parent = parent
        self._graph = parent._graph
        self.set_color(81, 54, 88)
        for port in gear.in_ports:
            self.add_input(port.basename)

        for port in gear.out_ports:
            self.add_output(port.basename)

        self.parent.add_node(self)

        self.NODE_NAME = gear.basename
        self.set_name(gear.basename)
        self.set_selected(False)
        self.gear = gear
        self.child_node_map = inst_children(self)

    def add_node(self, node):
        self.view.add_node(node)

    def set_pos(self, x, y):
        self.view.set_pos(x, y)

    def layout(self):
        self.view.layout()

    def connect(self, port1, port2):
        self.view.connect(port1, port2)


class NodeGear(Node):
    """
    This is a example test node.
    """

    # set a unique node identifier.
    __identifier__ = 'com.chantasticvfx'

    # set the initial default node name.
    NODE_NAME = 'My Node'

    def __hash__(self):
        return id(self)

    def __init__(self, gear, parent):
        super(NodeGear, self).__init__()
        self.gear = gear
        self._graph = parent._graph
        self.set_color(81, 54, 88)
        self.parent = parent
        self.NODE_NAME = gear.basename
        for port in gear.in_ports:
            self.add_input(port.basename)

        for port in gear.out_ports:
            self.add_output(port.basename)

        self.set_name(gear.basename)
        self.set_selected(False)
        self.parent.add_node(self)

    def layout(self):
        pass


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    # create node graph.
    graph = NodeGraph()

    viewer = graph.viewer()
    viewer.setWindowTitle('My Node Graph')
    viewer.resize(800, 500)
    viewer.show()

    add(2, 4) | shred

    bind('logger/util/level', INFO)
    print_hier()

    @reg_inject
    def make_graph(
            root=Inject('gear/hier_root'), params=False, fullname=False):

        top = Top(root, graph)
        top.layout()
        top.graph.center_selection()

    make_graph()

    app.exec_()
