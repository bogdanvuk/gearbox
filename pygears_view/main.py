#!/usr/bin/python
import sys
import os

from PySide2 import QtWidgets, QtCore, QtGui

from pygears_view.graph import NodeGraph
from pygears import bind
from pygears.conf.log import INFO
from pygears.common import add, shred
from pygears.util.print_hier import print_hier
from pygears.conf import Inject, reg_inject
from pygears_view.node import NodeItem
from pygears.sim.extens.sim_extend import SimExtend


class PyGearsView(SimExtend):
    @reg_inject
    def after_run(self, sim, outdir=Inject('sim/artifact_dir')):
        print(f"Here: {outdir}")
        os.path.join(outdir, 'pygears.vcd')
        main()


@reg_inject
def main(root=Inject('gear/hier_root')):
    # app = App(sys.argv)
    # app.installEventFilter(app)
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Source Code Pro", 13))

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

    graph.show()
    app.exec_()
