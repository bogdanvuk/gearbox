from PySide2 import QtCore, QtWidgets
from pygears import registry
from pygears.conf import MayInject, reg_inject, safe_bind
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
            # return True

    def after_run(self, sim):
        if self.pipe:
            self.pipe.send("after_run")


def sim_bridge():
    manager = PyGearsManager(address=('', 5000))
    manager.connect()

    sim_bridge = PyGearsClient()
    safe_bind('viewer/sim_bridge', sim_bridge)
    safe_bind('viewer/sim_proxy', manager)


class PyGearsClient(QtCore.QObject):
    after_run = QtCore.Signal()
    after_timestep = QtCore.Signal()
    sim_refresh = QtCore.Signal()
    message = QtCore.Signal(str)

    @reg_inject
    def __init__(self,
                 pipe=MayInject('viewer/sim_bridge_pipe'),
                 step=False,
                 refresh_interval=1000,
                 parent=None):
        super().__init__(parent)

        self.pipe = pipe
        self.step = step
        self.refresh_interval = refresh_interval

        QtWidgets.QApplication.instance().aboutToQuit.connect(self.quit)
        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)
        self.thrd.started.connect(self.run)
        self.thrd.start()

    def run(self):
        if self.refresh_interval:
            self.after_timestep_timer = QtCore.QTimer(self)
            self.after_timestep_timer.timeout.connect(self.refresh_timeout)
            self.after_timestep_timer.start(self.refresh_interval)

        while True:
            self.thrd.eventDispatcher().processEvents(
                QtCore.QEventLoop.AllEvents)

            if not self.pipe.poll(0.01):
                continue

            msg = self.pipe.recv()

            self.message.emit(msg)
            if msg == "after_run":
                self.after_timestep_timer.stop()
                self.after_run.emit()
                self.quit()
                return
            elif msg == "after_timestep" and self.step:
                self.after_timestep.emit()

    def quit(self):
        self.thrd.terminate()

    def refresh_timeout(self):
        self.sim_refresh.emit()
