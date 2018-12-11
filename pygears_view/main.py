#!/usr/bin/python
import queue
import sys
import threading

from PySide2 import QtGui, QtWidgets

from pygears_view.main_window import MainWindow
from pygears_view.graph import graph
from pygears_view.which_key import which_key
from pygears_view.gtkwave import gtkwave
from pygears_view.sniper import sniper
from pygears.conf import Inject, reg_inject, safe_bind, PluginBase, registry, bind
from .pygears_proxy import PyGearsBridgeServer, sim_bridge


class PyGearsView(PyGearsBridgeServer):
    def __init__(self, top=None, live=False):
        super().__init__(top)

        bind('sim/pygears_view', self)

        self.live = live
        self.pipe = None
        if live:
            registry('viewer/layers').insert(0, sim_bridge)

    @reg_inject
    def before_run(self, sim, outdir=Inject('sim/artifact_dir')):
        if self.live:
            self.queue = queue.Queue()

            thread = threading.Thread(target=main)
            thread.start()

        super().before_run(sim)

    def after_cleanup(self, sim):
        if not self.live:
            main()


@reg_inject
def main(pipe=None, layers=Inject('viewer/layers')):
    if pipe:
        safe_bind('viewer/sim_bridge_pipe', pipe)

    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("DejaVu Sans Mono", 13))

    main_window = MainWindow()

    for l in layers:
        l()

    main_window.show()
    app.exec_()


class SimPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('viewer/layers', [which_key, graph, gtkwave, sniper])
