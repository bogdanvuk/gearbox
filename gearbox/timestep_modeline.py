from PySide2 import QtCore
from pygears.conf import Inject, reg_inject


class TimestepModeline(QtCore.QObject):
    def __init__(self, buff):
        super().__init__()
        self.buff = buff
        self.buff.shown.connect(self.configure)
        self.buff.hidden.connect(self.reset)

        if self.buff.visible:
            self.configure()

    @reg_inject
    def configure(self, timekeep=Inject('gearbox/timekeep')):
        # TODO: Investiget why this is needed here
        if self.buff.window is None:
            return

        self.buff.window.modeline.add_field('timestep', '')
        timekeep.timestep_changed.connect(self.update)
        self.update()

    @reg_inject
    def reset(self, timekeep=Inject('gearbox/timekeep')):
        try:
            timekeep.timestep_changed.disconnect(self.update)
        except RuntimeError:
            pass

    @reg_inject
    def update(self, timestep=Inject('gearbox/timestep')):
        if timestep is None:
            timestep = '-'

        self.buff.window.modeline.set_field_text('timestep',
                                                 f'Timestep: {timestep}')

    def delete(self):
        self.reset()
