#!/usr/bin/python
import sys
import os
import multiprocessing

from PySide2 import QtGui, QtWidgets, QtCore

from pygears_view.main_window import MainWindow
from pygears_view.graph import graph
from pygears_view.which_key import which_key
from pygears_view.gtkwave import gtkwave
from pygears_view.sniper import sniper
from pygears.conf import Inject, reg_inject, safe_bind, PluginBase
from pygears.sim.extens.sim_extend import SimExtend


class PyGearsView(SimExtend):
    @reg_inject
    def before_run(self, sim, outdir=Inject('sim/artifact_dir')):
        self.pipe, qt_pipe = multiprocessing.Pipe()
        # main()
        p = multiprocessing.Process(target=main, args=(qt_pipe, ))
        p.start()

    def after_run(self, sim):
        self.pipe.send("after_run")


@reg_inject
def main(pipe, layers=Inject('viewer/layers')):
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Source Code Pro", 13))

    main_window = MainWindow(sim_pipe=pipe)

    for l in layers:
        l()

    main_window.show()
    app.exec_()


class SimPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('viewer/layers', [graph, which_key, gtkwave, sniper])
