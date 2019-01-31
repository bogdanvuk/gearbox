import queue
import time
import sys
from PySide2 import QtCore, QtWidgets
from pygears.conf import Inject, reg_inject, safe_bind, bind
from pygears.sim.extens.sim_extend import SimExtend


class PyGearsBridgeServer(SimExtend):
    def handle_event(self, name):
        self.event_name = name
        self.queue.put(name)
        self.queue.join()

        if self.done:
            sys.exit(0)

        # Let GUI thread do some work
        time.sleep(0.0001)

    def before_run(self, sim):
        self.handle_event('before_run')

    def after_timestep(self, sim, timestep):
        # if timestep > (1 << 15):
        self.handle_event('after_timestep')
        return True

    def after_run(self, sim):
        self.handle_event('after_run')


def sim_bridge():
    sim_bridge = PyGearsClient()
    safe_bind('viewer/sim_bridge', sim_bridge)


class PyGearsClient(QtCore.QObject):
    after_run = QtCore.Signal()
    after_timestep = QtCore.Signal()
    sim_refresh = QtCore.Signal()
    message = QtCore.Signal(str)

    @reg_inject
    def __init__(self,
                 plugin=Inject('sim/pygears_view'),
                 parent=None):
        super().__init__(parent)

        self.plugin = plugin
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

        while True:
            self.thrd.eventDispatcher().processEvents(
                QtCore.QEventLoop.AllEvents)

            try:
                msg = self.plugin.queue.get(0.001)
            except queue.Empty:
                continue

            msg = self.plugin.event_name
            if msg == "after_timestep":
                self.after_timestep.emit()

                if self._should_break():
                    self.running = False
                    self.sim_refresh.emit()
                    self.loop.exec_()
                    self.running = True

                self.plugin.queue.task_done()

            elif msg == "after_run":
                self.sim_refresh.emit()
                self.after_run.emit()
                self.quit()
                self.plugin.queue.task_done()
                return

            elif msg == "before_run":
                self.running = False
                self.loop.exec_()
                self.running = True
                self.plugin.queue.task_done()

    def quit(self):
        self.plugin.done = True
        self.thrd.quit()

    def refresh_timeout(self):
        self.sim_refresh.emit()
