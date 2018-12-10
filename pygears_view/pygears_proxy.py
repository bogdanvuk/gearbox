from PySide2 import QtCore, QtWidgets
from pygears import registry, find
from pygears.conf import MayInject, reg_inject, safe_bind
from multiprocessing.managers import BaseManager
from pygears.sim.extens.sim_extend import SimExtend
from pygears.core.sim_event import SimEvent


class PyGearsManager(BaseManager):
    pass


class RegistryProxy:
    def __init__(self, path):
        self.path = path

    def get(self):
        return registry(self.path)


class ActivityProxy:
    @reg_inject
    def get(self, activity=MayInject('sim/activity')):
        if activity:
            return activity.blockers

    @reg_inject
    def get_port_status(self, path, activity=MayInject('sim/activity')):
        if activity:
            port = find(path)
            return activity.get_port_status(port)


PyGearsManager.register('registry', RegistryProxy)
PyGearsManager.register('activity', ActivityProxy)


class PyGearsBridgeServer(SimExtend):
    def before_run(self, sim):
        if self.pipe:
            self.pipe.send("before_run")
            self.pipe.recv()

    def after_timestep(self, sim, timestep):
        if self.pipe:
            self.pipe.send("after_timestep")
            self.pipe.recv()
            return True

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
                 step=True,
                 refresh_interval=1000,
                 parent=None):
        super().__init__(parent)

        self.pipe = pipe
        self.step = step
        self.refresh_interval = refresh_interval
        self.loop = QtCore.QEventLoop(self)
        self.breakpoints = set()
        self.running = False

        QtWidgets.QApplication.instance().aboutToQuit.connect(self.quit)
        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)
        self.loop.moveToThread(self.thrd)
        self.thrd.started.connect(self.run)
        self.thrd.start()

    def cont(self):
        QtCore.QMetaObject.invokeMethod(self.loop, 'quit',
                                        QtCore.Qt.AutoConnection)

    def _should_break(self):
        triggered = False
        discard = []

        for b in self.breakpoints:
            trig, keep = b()
            if trig:
                triggered = True

            if not keep:
                discard.append(b)

        self.breakpoints.difference_update(discard)

        return triggered

    def run(self):

        # if self.refresh_interval:
        #     self.after_timestep_timer = QtCore.QTimer(self)
        #     self.after_timestep_timer.timeout.connect(self.refresh_timeout)
        #     self.after_timestep_timer.start(self.refresh_interval)

        refresh_counter = 0

        while True:
            self.thrd.eventDispatcher().processEvents(
                QtCore.QEventLoop.AllEvents)

            if not self.pipe.poll(0.001):
                continue

            msg = self.pipe.recv()

            self.message.emit(msg)
            if msg == "after_timestep" and self.step:
                self.after_timestep.emit()

                refresh_counter += 1
                if self._should_break():
                    refresh_counter = 0
                    self.running = False
                    self.sim_refresh.emit()
                    self.loop.exec_()
                    self.running = True

                elif refresh_counter >= self.refresh_interval:
                    self.sim_refresh.emit()
                    refresh_counter = 0

                self.pipe.send(' ')

            elif msg == "after_run":
                self.sim_refresh.emit()
                self.after_run.emit()
                self.quit()
                return
            elif msg == "before_run":
                self.running = False
                self.loop.exec_()
                self.running = True
                self.pipe.send(' ')

    def quit(self):
        self.thrd.quit()

    def refresh_timeout(self):
        self.sim_refresh.emit()
