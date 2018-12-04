#!/usr/bin/python
import sys
import os
import multiprocessing
import threading
from multiprocessing.managers import BaseManager, BaseProxy

from PySide2 import QtGui, QtWidgets, QtCore

from pygears_view.main_window import MainWindow
from pygears_view.graph import graph
from pygears_view.which_key import which_key
from pygears_view.gtkwave import gtkwave
from pygears_view.sniper import sniper
from pygears.conf import Inject, reg_inject, safe_bind, PluginBase
from pygears.sim.extens.sim_extend import SimExtend
from pygears import registry, bind
from .pygears_proxy import PyGearsBridge


class SimulatorProxy(BaseProxy):
    _exposed = ['proba', '__getattr__']

    def proba(self):
        return self._callmethod('proba')

    def timestep(self):
        return self._callmethod('__getattr__', 'timestep')


def get_registry(path):
    return registry(path)


def get_simulator():
    return registry('sim/simulator')


class PyGearsManager(BaseManager):
    pass


PyGearsManager.register('simproxy', get_simulator, SimulatorProxy)
PyGearsManager.register('registry', get_registry)


def manager_server(manager):
    print("Starting server!")
    manager.get_server().serve_forever()


class PyGearsView(SimExtend):
    @reg_inject
    def before_run(self, sim, outdir=Inject('sim/artifact_dir')):
        self.manager = PyGearsManager(address=('', 5000))
        thread = threading.Thread(
            target=self.manager.get_server().serve_forever)
        thread.start()

        self.pipe, qt_pipe = multiprocessing.Pipe()
        # main()
        p = multiprocessing.Process(target=main, args=(qt_pipe, ))
        p.start()

    def after_run(self, sim):
        self.pipe.send("after_run")


@reg_inject
def main(pipe, layers=Inject('viewer/layers')):
    manager = PyGearsManager(address=('', 5000))
    manager.connect()

    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Source Code Pro", 13))

    sim_bridge = PyGearsBridge(pipe)
    main_window = MainWindow()
    safe_bind('viewer/sim_bridge', sim_bridge)
    safe_bind('viewer/sim_proxy', manager)

    for l in layers:
        l()

    main_window.show()
    app.exec_()


class SimPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('viewer/layers', [graph, which_key, gtkwave, sniper])
