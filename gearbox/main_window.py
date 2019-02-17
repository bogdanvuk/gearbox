import os

from PySide2 import QtCore, QtWidgets, QtGui
from pygears.conf import PluginBase, registry, safe_bind, reg_inject, Inject, bind

from functools import partial
from .minibuffer import Minibuffer
from .layout import BufferStack


class Shortcut(QtCore.QObject):
    @reg_inject
    def __init__(self, domain, key, callback, main=Inject('gearbox/main')):
        super().__init__()

        if not isinstance(key, tuple):
            key = (key, )

        self._qshortcut = QtWidgets.QShortcut(QtGui.QKeySequence(*key), main)
        # self._qshortcut.activated.connect(callback)
        self._qshortcut.activated.connect(self.activated_slot)
        self._qshortcut.activatedAmbiguously.connect(main.shortcut_prefix)
        self.activated = self._qshortcut.activated
        # self._qshortcut.setContext(QtCore.Qt.ApplicationShortcut)
        # self._qshortcut.setWhatsThis(callback.__name__)
        main.add_shortcut(self)
        self.domain = domain
        self.key = key
        self.callback = callback
        main.domain_changed.connect(self.domain_changed)

    def activated_slot(self):
        # self._qshortcut.setEnabled(False)
        # self.callback()
        # QtWidgets.QApplication.instance().processEvents()
        # QtCore.QTimer.singleShot(100, self.callback)
        self.callback()
        # QtCore.QTimer.singleShot(2000, self.callback)
        # self._qshortcut.setEnabled(True)

    @property
    def enabled(self):
        return self._qshortcut.isEnabled()

    def domain_changed(self, domain):
        if ((self.domain is None and domain is not None and domain[0] != '_')
                or (self.domain == domain)):
            self._qshortcut.setEnabled(True)
        else:
            self._qshortcut.setEnabled(False)


@reg_inject
def register_prefix(domain, prefix, name, prefixes=Inject('gearbox/prefixes')):
    if not isinstance(prefix, tuple):
        prefix = (prefix, )

    prefixes[(domain, prefix)] = name


@reg_inject
def message(message, minibuffer=Inject('gearbox/minibuffer')):
    minibuffer.message(message)


def get_submenu(menu, title):
    for a in menu.actions():
        if a.menu():
            if a.menu().title() == title:
                return a.menu()


class MainWindow(QtWidgets.QMainWindow):

    key_cancel = QtCore.Signal()
    domain_changed = QtCore.Signal(str)
    shortcut_triggered = QtCore.Signal(object)
    resized = QtCore.Signal()

    def __init__(self, sim_pipe=None, parent=None):
        super().__init__(parent)

        self.setWindowIcon(
            QtGui.QIcon(
                os.path.join(os.path.dirname(__file__), 'gearbox.png')))

        desktop = QtWidgets.QDesktopWidget()
        desktop_frame = desktop.availableGeometry(self)
        self.resize(desktop_frame.size() * 0.7)
        self.move(desktop_frame.width() - self.width(), self.y())

        self._undo_stack = QtWidgets.QUndoStack(self)
        self.shortcuts = []

        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setSpacing(0)
        self.vbox.setMargin(0)
        self.vbox.setContentsMargins(0, 0, 0, 0)

        safe_bind('gearbox/main', self)

        self.buffers = BufferStack(main=self)
        self.vbox.addLayout(self.buffers)

        mainWidget = QtWidgets.QWidget()
        mainWidget.setLayout(self.vbox)
        mainWidget.setContentsMargins(0, 0, 0, 0)

        self.minibuffer = Minibuffer()
        # self.minibuffer.completed.connect(self._minibuffer_completed)
        safe_bind('gearbox/minibuffer', self.minibuffer)
        self.vbox.addLayout(self.minibuffer.view)

        self.setCentralWidget(mainWidget)

        self._init_actions()

        prefixes = registry('gearbox/prefixes')

        for domain, key, callback in registry('gearbox/shortcuts'):
            Shortcut(domain, key, callback)

            if not isinstance(key, tuple):
                key = (key, )

            if (domain is None) and (key[0] == QtCore.Qt.Key_Space):
                current_menu = self.menuBar()
                for i in range(2, len(key) + 1):
                    if i < len(key):
                        menu_name = prefixes.get((None, key[:i]), 'group').title()
                        submenu = get_submenu(current_menu, menu_name)
                        if submenu is None:
                            submenu = QtWidgets.QMenu(menu_name, self)
                            current_menu.addMenu(submenu)
                        current_menu = submenu
                    else:
                        action_name = callback.__name__
                        action = QtWidgets.QAction(action_name, self)
                        current_menu.addAction(action)
                        action.triggered.connect(callback)

    # def event(self, event):
    #     # if isinstance(event, (QtGui.QEnterEvent, QtGui.QHoverEvent)):
    #     #     return True

    #     # if (event.type() is QtCore.QEvent.Type.Leave) or (
    #     #         event.type() is QtCore.QEvent.Type.Enter) or (
    #     #             event.type() is QtCore.QEvent.Type.HoverMove):
    #     #     editor = registry('gearbox/editor')
    #     #     graph = registry('gearbox/graph')
    #     #     graph.clearFocus()
    #     #     editor.win.widget.activateWindow()
    #     #     editor.win.widget.setFocus()
    #     #     print(f'Set focus')

    #     print(f'Event: {event.type()}')
    #     return super().event(event)

    def add_shortcut(self, shortcut):
        self.shortcuts.append(shortcut)
        shortcut.activated.connect(partial(self.shortcut_trigger, shortcut))

    def shortcut_trigger(self, shortcut):
        self.shortcut_triggered.emit(shortcut)

    def _init_actions(self):
        QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_G),
            self).activated.connect(self._key_cancel_event)

        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape),
                            self).activated.connect(self._key_cancel_event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    def focusOutEvent(self, event):
        print("Focus Out")
        super().focusOutEvent(event)

    def add_buffer(self, widget):
        self.buffers.add(widget)

    def _key_cancel_event(self):
        self.key_cancel.emit()

    def shortcut_prefix(self):
        print("Ambiguous shortcut!")

    def change_domain(self, domain):
        bind('gearbox/domain', domain)
        self.domain_changed.emit(domain)


class MainWindowPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('gearbox/shortcuts', [])
        safe_bind('gearbox/prefixes', {})
