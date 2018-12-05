import threading
import multiprocessing

from PySide2 import QtCore
from pygears import registry
from pygears.conf import Inject, reg_inject, safe_bind
from multiprocessing.managers import BaseManager
from pygears.sim.extens.sim_extend import SimExtend


class PyGearsManager(BaseManager):
    pass


class RegistryProxy:
    def __init__(self, path):
        self.path = path

    def get(self):
        return registry(self.path)


PyGearsManager.register('registry', RegistryProxy)


class PyGearsBridgeServer(SimExtend):
    def after_timestep(self, sim, timestep):
        if self.pipe:
            self.pipe.send("after_timestep")

    def after_run(self, sim):
        if self.pipe:
            self.pipe.send("after_run")


def sim_bridge(pipe=Inject('viewer/sim_bridge_pipe')):
    manager = PyGearsManager(address=('', 5000))
    manager.connect()

    sim_bridge = PyGearsClient(pipe)
    safe_bind('viewer/sim_bridge', sim_bridge)
    safe_bind('viewer/sim_proxy', manager)


class PyGearsClient(QtCore.QObject):
    after_run = QtCore.Signal()
    after_timestep = QtCore.Signal()
    sim_refresh = QtCore.Signal()
    message = QtCore.Signal(str)

    def __init__(self, pipe, step=False, resfresh_interval=1000, parent=None):
        super().__init__(parent)

        if resfresh_interval:
            self.after_timestep_timer = QtCore.QTimer()
            self.after_timestep_timer.timeout.connect(self.refresh_timeout)
            self.after_timestep_timer.start(resfresh_interval)

        self.step = step
        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)
        self.thrd.started.connect(self.run)
        self.thrd.start()

    def run(self):
        nop = QtCore.QTimer(self)
        while True:
            nop.start()
            msg = self.pipe.recv()
            self.message.emit(msg)
            if msg == "after_run":
                self.after_timestep_timer.stop()
                self.after_run.emit()
            elif msg == "after_timestep" and self.step:
                self.after_timestep.emit()

    def refresh_timeout(self):
        self.sim_refresh.emit()
