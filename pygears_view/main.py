#!/usr/bin/python
import sys

from PySide2 import QtWidgets

from pygears_view.graph import NodeGraph
from pygears import bind
from pygears.conf.log import INFO
from pygears.common import add, shred
from pygears.util.print_hier import print_hier
from pygears.conf import Inject, reg_inject
from pygears_view.node import NodeItem


@reg_inject
def main(root=Inject('gear/hier_root')):
    app = QtWidgets.QApplication(sys.argv)

    # create node graph.
    graph = NodeGraph()

    viewer = graph.viewer()
    viewer.setWindowTitle('My Node Graph')
    viewer.resize(800, 500)
    viewer.setGeometry(500, viewer.y(), 800, 500)

    bind('logger/util/level', INFO)
    print_hier()

    top = NodeItem(root, graph)
    graph.top = top
    top.layout()
    top.graph.fit_all()

    # node = find_node_by_path(graph.top, 'shred')
    # print(node)

    graph.show()
    app.exec_()
