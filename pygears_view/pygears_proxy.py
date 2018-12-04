from PySide2 import QtCore


class PyGearsBridge(QtCore.QObject):
    after_run = QtCore.Signal()
    after_timestep = QtCore.Signal()

    def __init__(self, pipe, after_timestep_interval=1000, parent=None):
        super().__init__(parent)
        self.pipe = SimPipeListener(pipe)
        self.pipe.message.connect(self.message)
        if after_timestep_interval:
            self.after_timestep_timer = QtCore.QTimer(self)
            self.after_timestep_timer.timeout.connect(self.after_timestep_slot)
            self.after_timestep_timer.start(after_timestep_interval)

    def message(self, msg):
        if msg == "after_run":
            self.after_timestep_timer.stop()
            self.after_run.emit()

    def after_timestep_slot(self):
        self.after_timestep.emit()


class SimPipeListener(QtCore.QObject):
    message = QtCore.Signal(str)

    def __init__(self, pipe, after_timestep_interval=1000, parent=None):
        super().__init__(parent)
        self.pipe = pipe
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
                break
