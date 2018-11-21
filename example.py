#!/usr/bin/python
import os
import sys

from PySide2 import QtWidgets

from NodeGraphQt import NodeGraph, Node, Backdrop
from pygears import find, bind
from pygears.core.gear import InPort
from pygears.conf.log import INFO
from pygears.common import shred, add, ccat
from pygears.util.print_hier import print_hier
from pygears.core.hier_node import HierVisitorBase
from NodeGraphQt.base.commands import NodeAddedCmd
from pygears.conf import util_log, reg_inject, Inject
from grandalf.layouts import SugiyamaLayout
from grandalf.graphs import Vertex, Edge, Graph

# import example nodes from the "example_nodes" package
from example_nodes import simple_nodes, menu_node, text_input_node

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
        # node.add_node(graph_node)

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

    # registered nodes.
    reg_nodes = [
        Backdrop, NodeGear, menu_node.DropdownMenuNode, simple_nodes.FooNode,
        simple_nodes.BarNode, text_input_node.TextInputNode
    ]
    [graph.register_node(n) for n in reg_nodes]

    # my_node = graph.create_node(
    #     'com.chantasticvfx.NodeGear', name='test', pos=(310.0, 10.0))

    # foo_node = graph.create_node(
    #     'com.chantasticvfx.FooNode', name='Foo Node', pos=(-487.0, 141.0))

    # # create example "TextInputNode".
    # text_node = graph.create_node(
    #     'com.chantasticvfx.TextInputNode',
    #     name='Text Node',
    #     color='#6b273f',
    #     pos=(-488.0, -158.0))
    # text_node.set_disabled(True)

    # # create node with a combo box menu.
    # menu_node = graph.create_node(
    #     'com.chantasticvfx.DropdownMenuNode',
    #     name='Menu Node',
    #     color='#005341',
    #     pos=(279.0, -209.0))

    # ccat(0, 1, ccat(2, 3), ccat(3, 4)) | shred

    add(2, 4) | shred

    bind('logger/util/level', INFO)
    print_hier()

    class Visitor(HierVisitorBase):
        def __init__(self, graph, params=False, fullname=False):
            self.graph_node_hier = [graph]

        def Gear(self, node):
            if not node.child:
                graph_node = NodeGear(node)
            else:
                graph_node = HierGear(node)

            graph_node._graph = graph
            graph_node.update()
            gear_graph_node_map[node] = graph_node
            graph_node_gear_map[graph_node] = node

            graph._undo_stack.beginMacro('created node')
            graph._undo_stack.push(NodeAddedCmd(graph, graph_node, None))
            graph._undo_stack.endMacro()

            if node.parent in gear_graph_node_map:
                gear_graph_node_map[node.parent].add_node(graph_node)

            parent = self.graph_node_hier[-1]
            parent.add_node(graph_node)
            self.graph_node_hier.append(graph_node)

            super().HierNode(node)

            self.graph_node_hier.pop()

    @reg_inject
    def make_graph(
            root=Inject('gear/hier_root'), params=False, fullname=False):

        top = Top(root, graph)
        top.layout()
        top.graph.center_selection()

        # v = Visitor(params, fullname)

        # gear_graph_node_map[root] = Top(root)
        # graph_node_gear_map[gear_graph_node_map[root]] = root

        # v.visit(root)

        # for node, graph_node in gear_graph_node_map.items():
        #     if node is root:
        #         continue

        #     if node.child:
        #         graph_node.collapse()

        #     for port in node.in_ports:
        #         for consumer in port.consumer.consumers:
        #             consumer_graph_node = gear_graph_node_map[consumer.gear]
        #             src_port = graph_node.input(port.index)
        #             src_port.connect_to(
        #                 consumer_graph_node.input(consumer.index))

        #     for port in node.out_ports:
        #         for consumer in port.consumer.consumers:
        #             consumer_graph_node = gear_graph_node_map[consumer.gear]

        #             if isinstance(consumer, InPort):
        #                 src_port = graph_node.output(port.index)
        #                 dest_port = consumer_graph_node.input(consumer.index)
        #             else:
        #                 src_port = consumer_graph_node.output(consumer.index)
        #                 dest_port = graph_node.output(port.index)

        #             graph_node.parent.connect(src_port, dest_port)

        # gear_graph_node_map[root].layout()

        # for node, graph_node in gear_graph_node_map.items():
        #     if node is root:
        #         continue

        #     if node.child:
        #         graph_node.collapse()
        #         graph_node.layout()

    make_graph()
    # V = [n.vertex for n in graph_node_gear_map]
    # print(V)
    # g = Graph(V, E)

    # class defaultview(object):
    #     w, h = 100, 200

    # for v in V:
    #     v.view = defaultview()
    # sug = SugiyamaLayout(g.C[0])
    # sug.init_all(roots=[V[1]])
    # sug.draw()

    # for n in graph_node_gear_map:
    #     n.set_pos(n.vertex.view.xy[1] - 500, n.vertex.view.xy[0])

    # for l in sug.layers:
    #     for n in l:
    #         print(n.view.xy, end='')

    #     print()

    # # change node icon.
    # this_path = os.path.dirname(os.path.abspath(__file__))
    # icon = os.path.join(this_path, 'example', 'example_icon.png')
    # bar_node = graph.create_node('com.chantasticvfx.BarNode')
    # bar_node.set_icon(icon)
    # bar_node.set_name('Bar Node')
    # bar_node.set_pos(-77.0, 17.0)

    # # connect the nodes
    # foo_node.set_output(0, bar_node.input(2))
    # menu_node.set_input(0, bar_node.output(1))
    # bar_node.set_input(0, text_node.output(0))

    app.exec_()
