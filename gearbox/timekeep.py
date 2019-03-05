from functools import partial
from PySide2 import QtCore
from pygears.sim import timestep as sim_timestep
from pygears.conf import reg_inject, Inject, inject_async, bind


@reg_inject
def timestep(timekeep=Inject('gearbox/timekeep')):
    return timekeep.timestep


@reg_inject
def max_timestep(timekeep=Inject('gearbox/timekeep')):
    return timekeep.max_timestep


@reg_inject
def timetep_event_register_connect(slot, timekeep=Inject('gearbox/timekeep')):
    timekeep.timestep_changed.connect(slot)


def timestep_event_register(slot):
    inject_async(partial(timetep_event_register_connect, slot=slot))


def timekeep(sim_bridge=Inject('gearbox/sim_bridge')):
    bind('gearbox/timekeep', TimeKeep())


class TimeKeep(QtCore.QObject):
    timestep_changed = QtCore.Signal(int)

    @reg_inject
    def __init__(self,
                 cont_refresh_step=2000,
                 sim_bridge=Inject('gearbox/sim_bridge')):
        super().__init__()
        self._timestep = None
        self._time_target = None
        self._cont_refresh_step = cont_refresh_step
        bind('gearbox/timestep', self.max_timestep)
        sim_bridge.after_timestep.connect(self.sim_break)
        sim_bridge.model_closed.connect(self.model_closed)
        sim_bridge.script_loaded.connect(self.model_loaded)

    def model_loaded(self):
        self._timestep = None
        self._time_target = None
        self.timestep_changed.emit(self._timestep)

    def model_closed(self):
        self._timestep = None
        self._time_target = None

    def sim_break(self):
        self.timestep = self.max_timestep

    @property
    def timestep(self):
        return self._timestep

    def break_on_timestep(self):
        if self._timestep is None:
            self._timestep = 0

        if self.max_timestep == self._timestep + self._cont_refresh_step:
            self.timestep = self.max_timestep

        if self.max_timestep == self._time_target:
            return True, False
        else:
            return False, True

    @timestep.setter
    @reg_inject
    def timestep(self, val, sim_bridge=Inject('gearbox/sim_bridge')):
        if (self.max_timestep is None) or (val > self.max_timestep):
            self._time_target = val
            sim_bridge.breakpoint(self.break_on_timestep)
            if not sim_bridge.running:
                sim_bridge.cont()
        else:
            if val != self._timestep:
                self._timestep = val
                bind('gearbox/timestep', self._timestep)
                self.timestep_changed.emit(self._timestep)

    @property
    def max_timestep(self):
        return sim_timestep()
