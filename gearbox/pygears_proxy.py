import functools
import logging
import os
import queue
import runpy
import sys

from PySide2 import QtCore, QtWidgets

from pygears import MultiAlternativeError
from pygears.conf import Inject, PluginBase, inject, reg
from pygears.conf.trace import pygears_excepthook, log_exception
from pygears.sim import SimFinish, sim, SimSetupDone
from pygears.sim.extens.sim_extend import SimExtend
from pygears.sim.modules import SimVerilated

from .node_model import find_cosim_modules

# from jinja2.debug import fake_exc_info


class EmptyHierarchy(Exception):
    pass


class Gearbox(QtCore.QObject, SimExtend):
    sim_event = QtCore.Signal(str)

    def __init__(self,
                 live=True,
                 reload=True,
                 standalone=False,
                 sim_queue=None):

        QtCore.QObject.__init__(self)
        self.loop = QtCore.QEventLoop(self)

        reg['sim/gearbox'] = self

        # self.queue = sim_queue
        # if self.queue is None:
        #     self.queue = queue.Queue()

        self.breakpoints = set()
        self.live = live
        self.done = False
        self.reload = reload
        self.standalone = standalone
        self.running = False

        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)
        self.thrd.started.connect(self.run)
        self.thrd.start()

    def __call__(self):
        SimExtend.__init__(self)
        return self

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

    def cont(self):
        QtCore.QMetaObject.invokeMethod(self.loop, 'quit',
                                        QtCore.Qt.AutoConnection)

    def handle_event(self, name):
        if self.done:
            return

        # print(f'{timestep()} : {name}, done: {self.done}')
        if (name in ['after_cleanup', 'before_run']
                or (name == 'after_timestep' and self._should_break())):

            self.running = False
            self.sim_event.emit(name)

            QtCore.QThread.currentThread().eventDispatcher().processEvents(
                QtCore.QEventLoop.AllEvents)

            self.loop.exec_()
            self.running = True
        else:
            # print("Here?")
            QtCore.QThread.yieldCurrentThread()
            QtCore.QThread.currentThread().usleep(10)
            # QtCore.QThread.currentThreadId().msleep(10)
            # Let GUI thread do some work
            # time.sleep(0.0001)

        # print('Back to the simulator')

        if self.done and not name == 'after_cleanup':
            raise SimFinish
            # sys.exit(0)

    def before_run(self, sim):
        # Gearbox has to be last of all plugins to receive 'after_timestep'
        # event, so that for an example VCD plugin finished flushing waveforms
        e = sim.events['after_timestep']
        i = e.index(self.after_timestep)
        del e[i]
        e.append(self.after_timestep)

        self.handle_event('before_run')

    # def at_exit(self, sim):
    #     self.handle_event('at_exit')

    def after_timestep(self, sim, timestep):
        self.handle_event('after_timestep')
        return True

    def after_cleanup(self, sim):
        self.handle_event('after_cleanup')

    def before_setup(self, sim):
        # Gearbox has to be last of all plugins to receive 'after_timestep'
        # event, so that for an example VCD plugin finished flushing waveforms
        e = sim.events['before_run']
        i = e.index(self.before_run)
        del e[i]
        e.append(self.before_run)

        if self.live:
            for m in find_cosim_modules():
                if isinstance(m, SimVerilated):
                    m.vcd_fifo = True
                    m.shmidcat = True

    def run(self):
        # self.plugin = Gearbox()
        try:
            sim(extens=[self], check_activity=False)
        except Exception as e:
            # import traceback
            # traceback.print_exc()
            log_exception(e)
            self.sim_event.emit('exception')

            # import traceback
            # import pdb
            # extype, value, tb = sys.exc_info()
            # traceback.print_exc()
            # pdb.post_mortem(tb)

        self.thrd.quit()

    # def after_cleanup(self, sim):
    #     if not self.live:
    #         main()


def sim_bridge():
    sim_bridge = PyGearsClient()
    reg['gearbox/sim_bridge'] = sim_bridge
    return sim_bridge


def _err_reconnect_dfs(err, issue_id, path):
    if isinstance(err, MultiAlternativeError):
        if hasattr(err, 'root_gear'):
            path.append(err.root_gear)

        for e in err.errors:
            ret, issue_id = _err_reconnect_dfs(e[2], issue_id, path)
            if ret:
                return True, issue_id
        else:
            if hasattr(err, 'root_gear'):
                path.pop()
            return False, issue_id

    elif issue_id == 0:
        if hasattr(err, 'root_gear'):
            path.append(err.root_gear)

            # if err.root_gear is not err.gear:
            #     path.append(err.gear)

        return True, -1
    else:
        return False, issue_id - 1


def err_reconnect_dfs(err, issue_id):
    path = []
    _err_reconnect_dfs(err, issue_id, path)
    return path


class PyGearsClient(QtCore.QObject):
    script_loading_started = QtCore.Signal()
    script_loaded = QtCore.Signal()
    script_closed = QtCore.Signal()
    model_closed = QtCore.Signal()
    model_loaded = QtCore.Signal()
    sim_init = QtCore.Signal()
    message = QtCore.Signal(str)

    # These are called automatically by handle_event
    after_cleanup = QtCore.Signal()
    after_timestep = QtCore.Signal()
    at_exit = QtCore.Signal()

    @inject
    def __init__(
            self,
            parent=None,
            standalone=False,
    ):
        super().__init__(parent)

        # self.loop = QtCore.QEventLoop(self)
        self.simulating = False
        self.invoke_queue = queue.Queue()
        self.queue = None
        self.closing = False
        self.err = None
        self.cur_model_issue_id = None
        self.pygears_proc = None
        self.model_was_loaded = True

        # QtWidgets.QApplication.instance().aboutToQuit.connect(self.quit)
        # self.script_closed.connect(QtWidgets.QApplication.instance().quit)
        # QtWidgets.QApplication.instance().aboutToQuit.connect(self.close_script)

        self.start_thread()

    @property
    def running(self):
        if self.pygears_proc:
            return self.pygears_proc.running
        else:
            return False

    def breakpoint(self, func):
        self.pygears_proc.breakpoints.add(func)

    def start_thread(self):
        self.thrd = QtCore.QThread()
        reg['gearbox/main/threads'].add(self.thrd)
        self.moveToThread(self.thrd)
        # self.loop.moveToThread(self.thrd)
        # self.thrd.started.connect(self.run)
        self.thrd.start()

    def invoke_method(self, name, *args, **kwds):
        self.invoke(getattr(self, name), *args, **kwds)

    def invoke(self, _func, *args, **kwds):
        self.invoke_queue.put(functools.partial(_func, *args, **kwds))

        QtCore.QMetaObject.invokeMethod(self, "invoke_handler",
                                        QtCore.Qt.QueuedConnection)

    @QtCore.Slot()
    def invoke_handler(self):
        f = self.invoke_queue.get()
        f()

    def run_sim(self):
        print("Running sim")

        self.pygears_proc = Gearbox()
        self.pygears_proc.sim_event.connect(self.handle_event)
        self.simulating = True

        # self.queue = self.pygears_proc.queue
        print("Sim run")

    def handle_event(self, name):
        if name == 'after_cleanup':
            sim_exception = reg['sim/exception']
            if sim_exception:
                log_exception(sim_exception)

            self.simulating = False

        if (name == 'before_run') or (name == 'exception' and not self.model_was_loaded):
            self.model_was_loaded = True
            self.model_loaded.emit()
        else:
            getattr(self, name).emit()

    def close_model(self):
        if self.cur_model_issue_id is not None:
            path = err_reconnect_dfs(self.err, self.cur_model_issue_id)
            for gear in path:
                gear.parent.child.remove(gear)
                for port in gear.in_ports:
                    if port.basename not in gear.const_args:
                        port.producer.consumers.remove(port)
                    else:
                        gear.parent.child.remove(port.producer.producer.gear)

        self.cur_model_issue_id = None
        self.model_closed.emit()

    def close_script(self):
        if reg['gearbox/model_script_name']:
            print("Closing script!")
            if self.pygears_proc:
                self.pygears_proc.done = True
                self.pygears_proc.cont()
                self.pygears_proc.thrd.wait()

            print("Closing script - signals!")
            self.model_closed.emit()
            self.script_closed.emit()

        self.thrd.quit()

    @property
    @inject
    def cur_model_issue(self, issues=Inject('trace/issues')):
        if self.cur_model_issue_id is not None:
            return issues[self.cur_model_issue_id]

        return None

    @property
    @inject
    def cur_model_issue_path(self):
        if self.cur_model_issue_id is not None:
            issue_path = err_reconnect_dfs(self.err, self.cur_model_issue_id)
            issue = self.cur_model_issue
            if hasattr(issue, 'gear') and issue.gear is not issue_path[-1]:
                issue_path.append(issue.gear)

            return issue_path

        return None

    def set_err_model(self, issue_id):
        if self.cur_model_issue_id is not None:
            self.close_model()

        self.cur_model_issue_id = issue_id
        path = err_reconnect_dfs(self.err, issue_id)
        for gear in path:
            gear.parent.add_child(gear)
            for port in gear.in_ports:
                if port.basename not in self.const_args:
                    port.producer.connect(port)
                else:
                    gear.parent.add_child(port.producer.producer.gear)

        self.model_loaded.emit()

    def run_model(self, script_fn, func=None, funcargs=None):
        artifacts_dir = reg['results-dir']
        if not artifacts_dir:
            artifacts_dir = os.path.join(os.path.dirname(script_fn), 'build')
            reg['results-dir'] = artifacts_dir
            print(f"Artifacts dir: {artifacts_dir}")

        os.makedirs(artifacts_dir, exist_ok=True)
        sys.path.append(os.path.dirname(script_fn))
        reg['trace/ignore'].append(os.path.dirname(__file__))
        reg['trace/ignore'].append(runpy.__file__)
        compilation_log_fn = os.path.join(artifacts_dir, 'compilation.log')
        reg['gearbox/compilation_log_fn'] = compilation_log_fn
        reg['debug/trace'] = ['*']

        os.system(f'rm -rf {compilation_log_fn}')

        # import pdb; pdb.set_trace()
        old_handlers = {}
        for name in reg['logger']:
            if name in logging.root.manager.loggerDict:
                logger = logging.getLogger(name)
                old_handlers[name] = logger.handlers.copy()
                logger.handlers.clear()
                logger.addHandler(
                    logger.get_logger_handler(
                        logging.FileHandler(compilation_log_fn)))

        reg['gearbox/model_script_name'] = script_fn
        print(f'Script loading started')
        self.script_loading_started.emit()

        self.err = None
        self.cur_model_issue_id = None
        reg['sim/dryrun'] = True
        try:
            if func is None:
                runpy.run_path(script_fn)
            else:
                func(**funcargs)
        except SimSetupDone:
            pass
        except Exception as e:
            self.err = e
        finally:
            reg['sim/dryrun'] = False

        self.script_loaded.emit()

        if not self.err:
            root = reg['gear/root']
            if not root.child:
                self.err = EmptyHierarchy('No PyGears model created')
                exc_info = fake_exc_info((EmptyHierarchy, self.err, None),
                                         script_fn, 0)
                self.err = self.err.with_traceback(exc_info[2])

        if self.err is not None:
            pygears_excepthook(type(self.err), self.err,
                               self.err.__traceback__)

        if self.err is None:
            self.invoke_method('run_sim')

    def cont(self):
        if self.simulating:
            self.pygears_proc.cont()

    # def quit(self):
    #     print("aboutToQuit proxy")
    #     self.thrd.quit()


class MainWindowPlugin(PluginBase):
    @classmethod
    def bind(cls):
        reg['gearbox/model_script_name'] = None
        reg['gearbox/compilation_log_fn'] = None
