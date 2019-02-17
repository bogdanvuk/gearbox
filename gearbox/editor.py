from .foreign_win import ForeignWindow
from PySide2 import QtCore

from pygears.conf import Inject, reg_inject, MayInject, bind
from .layout import Buffer


class GtkWaveBuffer(Buffer):
    def __init__(self, instance, name):
        self.name = name
        self.instance = instance
        self.instance.initialized.connect(self.load)
        self.window = None

    @reg_inject
    def load(self, main=Inject('gearbox/main'), layout=Inject('gearbox/layout')):
        main.add_buffer(self)
        # window = layout.active_window()
        # new_window = window.split_vertically()
        # new_window.place_buffer(self)

    def activate(self):
        super().activate()
        self.instance.widget.activateWindow()

    def deactivate(self):
        super().deactivate()

    @property
    def view(self):
        return self.instance.widget

    @property
    def domain(self):
        return 'gtkwave'


class Editor(QtCore.QObject):
    def __init__(self, cmd):
        self.win = ForeignWindow(cmd)
        self.buffer = GtkWaveBuffer(self.win, f'editor')
