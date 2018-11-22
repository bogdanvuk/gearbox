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

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    # create node graph.
    graph = NodeGraph()

    viewer = graph.viewer()
    viewer.setWindowTitle('My Node Graph')
    viewer.resize(800, 500)
    viewer.setGeometry(500, viewer.y(), 800, 500)
    viewer.show()

    add(2, 4) | shred
    # const(val=2) | shred

    bind('logger/util/level', INFO)
    print_hier()

    @reg_inject
    def make_graph(
            root=Inject('gear/hier_root'), params=False, fullname=False):

        top = NodeItem(root, graph)
        top.layout()
        top.graph.center_selection()

    make_graph()

    app.exec_()
