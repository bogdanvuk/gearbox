#!/usr/bin/python
import sys
import os

from PySide2 import QtGui, QtWidgets

from pygears_view.main_window import MainWindow
from pygears_view.graph import graph
from pygears_view.which_key import which_key
from pygears_view.gtkwave import gtkwave
from pygears_view.sniper import sniper
from pygears.conf import Inject, reg_inject, safe_bind, PluginBase
from pygears.sim.extens.sim_extend import SimExtend


class PyGearsView(SimExtend):
    # @reg_inject
    # def __init__(self, layers=Inject('viewer/layers')):
    #     super().__init__()
        # self.layers = layers

    @reg_inject
    def after_run(self, sim, outdir=Inject('sim/artifact_dir')):
        os.path.join(outdir, 'pygears.vcd')
        main()


@reg_inject
def main(layers=Inject('viewer/layers')):
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Source Code Pro", 13))

    main_window = MainWindow()

    for l in layers:
        l()

    main_window.show()
    app.exec_()


class SimPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('viewer/layers', [graph, which_key, gtkwave, sniper])
