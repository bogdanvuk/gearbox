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


class TimeKeep(QtCore.QObject):
    timestep_changed = QtCore.Signal(int)

    def __init__(self, cont_refresh_step=2000):
        super().__init__()
        self._timestep = sim_timestep()
        self._time_target = None
        self._cont_refresh_step = cont_refresh_step
        bind('gearbox/timekeep', self)
        bind('gearbox/timestep', self.max_timestep)
        inject_async(self.sim_bridge_connect)

    def sim_bridge_connect(self, sim_bridge=Inject('gearbox/sim_bridge')):
        sim_bridge.sim_refresh.connect(self.sim_break)

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
            sim_bridge.breakpoints.add(self.break_on_timestep)
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
