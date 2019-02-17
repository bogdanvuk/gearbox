import runpy
import functools
import threading
import queue
import time
import sys
from PySide2 import QtCore, QtWidgets
from pygears.conf import Inject, reg_inject, safe_bind, bind
from pygears.sim.extens.sim_extend import SimExtend
from .node_model import find_cosim_modules
from pygears.sim.modules import SimVerilated
from pygears.conf import Inject, bind, reg_inject, registry, safe_bind
from pygears.sim import sim
from pygears import clear


class Gearbox(SimExtend):
    def __init__(self,
                 top=None,
                 live=True,
                 reload=True,
                 standalone=False,
                 sim_queue=None):

        super().__init__(top)

        bind('sim/gearbox', self)

        self.queue = sim_queue
        if self.queue is None:
            self.queue = queue.Queue()

        self.live = live
        self.done = False
        self.reload = reload
        self.standalone = standalone

    def handle_event(self, name):
        print(f"Sending event: {name}")
        self.queue.put(name)
        self.queue.join()
        print(f"Event done: {name}")

        if self.done:
            sys.exit(0)

        # Let GUI thread do some work
        time.sleep(0.0001)

    @reg_inject
    def before_run(self, sim, outdir=Inject('sim/artifact_dir')):
        if self.live and not self.standalone:
            registry('gearbox/layers').insert(0, sim_bridge)
            thread = threading.Thread(target=main)
            thread.start()

        self.handle_event('before_run')

    def after_timestep(self, sim, timestep):
        # if timestep > (1 << 15):
        self.handle_event('after_timestep')
        return True

    def after_run(self, sim):
        self.handle_event('after_run')

    def before_setup(self, sim):
        if self.live:
            for m in find_cosim_modules():
                if isinstance(m, SimVerilated):
                    m.vcd_fifo = True
                    m.shmidcat = True

    def after_cleanup(self, sim):
        if not self.live:
            main()


def sim_bridge():
    sim_bridge = PyGearsClient()
    safe_bind('gearbox/sim_bridge', sim_bridge)
    return sim_bridge


class PyGearsProc(QtCore.QObject):
    def __init__(self):
        super().__init__()

        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)
        self.thrd.started.connect(self.run)
        self.thrd.finished.connect(self.quit)

        self.queue = queue.Queue()
        self.plugin = functools.partial(
            Gearbox, standalone=True, sim_queue=self.queue)

        self.thrd.start()

    def run(self):
        try:
            sim(outdir='build', extens=[self.plugin])
        except Exception as e:
            import traceback
            traceback.print_exc()

    def quit(self):
        self.thrd.quit()


class PyGearsClient(QtCore.QObject):
    model_loaded = QtCore.Signal()
    sim_started = QtCore.Signal()
    after_run = QtCore.Signal()
    after_timestep = QtCore.Signal()
    sim_refresh = QtCore.Signal()
    message = QtCore.Signal(str)

    @reg_inject
    def __init__(
            self,
            parent=None,
            standalone=False,
    ):
        super().__init__(parent)

        self.loop = QtCore.QEventLoop(self)
        self.breakpoints = set()
        self.running = False
        self.invoke_queue = queue.Queue()
        self.queue = None

        QtWidgets.QApplication.instance().aboutToQuit.connect(self.quit)
        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)
        self.loop.moveToThread(self.thrd)
        self.thrd.started.connect(self.run)
        self.thrd.start()

    def invoke_method(self, name, *args, **kwds):
        self.invoke(getattr(self, name), *args, **kwds)

    def invoke(self, func, *args, **kwds):
        self.invoke_queue.put(functools.partial(func, *args, **kwds))

        QtCore.QMetaObject.invokeMethod(self, "invoke_handler",
                                        QtCore.Qt.QueuedConnection)

    @QtCore.Slot()
    def invoke_handler(self):
        f = self.invoke_queue.get()
        f()

    def run_sim(self):
        self.pygears_proc = PyGearsProc()
        self.queue = self.pygears_proc.queue

    def run_model(self, script_fn):
        gearbox_registry = registry('gearbox')
        clear()
        bind('gearbox', gearbox_registry)
        runpy.run_path(script_fn)
        bind('gearbox/model_script_name', script_fn)
        self.model_loaded.emit()

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

    def queue_loop(self):
        while True:

            self.thrd.eventDispatcher().processEvents(
                QtCore.QEventLoop.AllEvents)

            try:
                msg = self.queue.get(0.001)
            except queue.Empty:
                continue

            if msg == "after_timestep":
                self.after_timestep.emit()

                if self._should_break():
                    self.running = False
                    self.sim_refresh.emit()
                    self.loop.exec_()
                    self.running = True

                self.queue.task_done()

            elif msg == "after_run":
                self.sim_refresh.emit()
                self.after_run.emit()
                self.quit()
                self.queue.task_done()
                return

            elif msg == "before_run":
                self.sim_started.emit()
                self.running = False
                self.loop.exec_()
                self.running = True
                self.queue.task_done()

    def run(self):
        while self.queue is None:
            self.thrd.eventDispatcher().processEvents(
                QtCore.QEventLoop.AllEvents)
            time.sleep(0.1)

        try:
            self.queue_loop()
        except Exception:
            import traceback
            traceback.print_exc()

    def quit(self):
        # self.plugin.done = True
        self.thrd.quit()

    def refresh_timeout(self):
        self.sim_refresh.emit()
