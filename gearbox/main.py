#!/usr/bin/python
import runpy
import queue
import sys
import threading

from PySide2 import QtGui, QtWidgets

from gearbox.main_window import MainWindow
from gearbox.graph import graph
from gearbox.which_key import which_key
from gearbox.gtkwave import gtkwave
from gearbox.sniper import sniper
from gearbox.description import description
from pygears.sim.extens.vcd import SimVCDPlugin
from pygears.conf import Inject, reg_inject, safe_bind, PluginBase, registry, bind, MayInject
from .pygears_proxy import PyGearsBridgeServer, sim_bridge
from .saver import get_save_file_path
from .node_model import find_cosim_modules
from .timekeep import TimeKeep
from pygears.sim.modules import SimVerilated


class Gearbox(PyGearsBridgeServer):
    def __init__(self, top=None, live=True, reload=True):
        super().__init__(top)

        bind('sim/gearbox', self)

        self.live = live
        self.pipe = None
        self.done = False
        self.reload = reload

        if live:
            registry('viewer/layers').insert(0, sim_bridge)

    def before_setup(self, sim):
        for m in find_cosim_modules():
            if isinstance(m, SimVerilated):
                m.vcd_fifo = True
                m.shmidcat = True

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

    app.setWindowIcon(QtGui.QIcon('gearbox.png'))
    app.setFont(QtGui.QFont("DejaVu Sans Mono", 11))

    timekeep = TimeKeep()

    main_window = MainWindow()

    import os
    import __main__
    main_window.setWindowIcon(
        QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'gearbox.png')))
    main_window.setWindowTitle(f'Gearbox - {os.path.abspath(__main__.__file__)}')

    for l in layers:
        l()

    main_window.show()
    app.exec_()


@reg_inject
def reloader(
        outdir=MayInject('sim/artifact_dir'), plugin=Inject('sim/gearbox')):
    if plugin.reload:
        try:
            runpy.run_path(get_save_file_path())
        except Exception as e:
            print(f'Loading save file failed: {e}')


class SimPlugin(SimVCDPlugin):
    @classmethod
    def bind(cls):
        safe_bind('viewer/layers',
                  [which_key, graph, gtkwave, sniper, description, reloader])
        safe_bind('sim/extens/vcd/shmidcat', True)
        safe_bind('sim/extens/vcd/vcd_fifo', True)
