import os

from PySide2 import QtCore, QtWidgets, QtGui
from pygears.conf import PluginBase, inject, Inject, MayInject, reg

from functools import partial
from .minibuffer import Minibuffer
from .layout import BufferStack
from .dbg import dbg_connect


class Action(QtWidgets.QAction):
    activated = QtCore.Signal()

    @inject
    def __init__(self, domain, key, callback, name, main=Inject('gearbox/main/inst')):
        super().__init__(name.title(), parent=main)

        if not isinstance(key, tuple):
            key = (key, )

        self.setShortcut(QtGui.QKeySequence(*key))
        self.setShortcutVisibleInContextMenu(True)
        self.domain = domain
        self.key = key
        self.callback = callback
        self.name = name
        main.domain_changed.connect(self.domain_changed)
        main.add_shortcut(self)
        dbg_connect(self.triggered, callback)
        self.triggered.connect(self.activated_slot)

    def activated_slot(self):
        self.activated.emit()

    @property
    def enabled(self):
        return self.isEnabled()

    def domain_changed(self, domain):
        if ((self.domain is None and domain is not None and domain[0] != '_')
                or (self.domain == domain)):
            self.setEnabled(True)
        else:
            self.setEnabled(False)


class Shortcut(QtCore.QObject):
    @inject
    def __init__(self, domain, key, callback, name, main=Inject('gearbox/main/inst')):
        super().__init__()

        if not isinstance(key, tuple):
            key = (key, )

        self._qshortcut = QtWidgets.QShortcut(QtGui.QKeySequence(*key), main)
        # self._qshortcut.activated.connect(callback)
        dbg_connect(self._qshortcut.activated, self.activated_slot)
        self._qshortcut.activatedAmbiguously.connect(main.shortcut_prefix)
        self.activated = self._qshortcut.activated
        # self._qshortcut.setContext(QtCore.Qt.ApplicationShortcut)
        # self._qshortcut.setWhatsThis(callback.__name__)
        main.add_shortcut(self)
        self.domain = domain
        self.key = key
        self.callback = callback
        self.name = name
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


@inject
def register_prefix(domain, prefix, name, prefixes=Inject('gearbox/prefixes')):
    if not isinstance(prefix, tuple):
        prefix = (prefix, )

    prefixes[(domain, prefix)] = name


@inject
def message(message, minibuffer=Inject('gearbox/minibuffer')):
    minibuffer.message(message)


class MainWindow(QtWidgets.QMainWindow):

    key_cancel = QtCore.Signal()
    domain_changed = QtCore.Signal(object)
    shortcut_triggered = QtCore.Signal(object)
    resized = QtCore.Signal()

    def __init__(self, sim_pipe=None, parent=None):
        super().__init__(parent)

        self.setWindowIcon(
            QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'gearbox.png')))

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

        reg['gearbox/main/inst'] = self

        self.buffers = BufferStack(main=self)
        self.vbox.addLayout(self.buffers)

        mainWidget = QtWidgets.QWidget()
        mainWidget.setLayout(self.vbox)
        mainWidget.setContentsMargins(0, 0, 0, 0)

        self.minibuffer = Minibuffer()
        # self.minibuffer.completed.connect(self._minibuffer_completed)
        reg['gearbox/minibuffer'] = self.minibuffer
        reg['gearbox/domain'] = None

        self.vbox.addLayout(self.minibuffer.view)

        self.setCentralWidget(mainWidget)

        self._init_actions()

        # for domain, key, callback, name in reg['gearbox/shortcuts']:
        #     Shortcut(domain, key, callback, name)

        self.create_menus()

        if not reg['gearbox/main/menus']:
            self.menuBar().hide()

    @inject
    def closeEvent(
        self,
        event,
        script_fn=Inject('gearbox/model_script_name'),
        sim_bridge=Inject('gearbox/sim_bridge')):
        if script_fn:
            event.ignore()
            sim_bridge.invoke_method('close_script')
        else:
            super().closeEvent(event)

    @inject
    def create_menus(
        self, prefixes=Inject('gearbox/prefixes'), shortcuts=Inject('gearbox/shortcuts')):
        for domain, key, callback, name in reg['gearbox/shortcuts']:
            if not isinstance(key, tuple):
                key = (key, )

            current_menu = self.menuBar()
            start_skip = 1
            if (domain is None):
                if (key[0] != QtCore.Qt.Key_Space):
                    Shortcut(domain, key, callback, name)

                start_skip = 2

            else:
                submenu = self.get_or_create_submenu(current_menu, domain.title())
                action = self.get_subaction(current_menu, domain.title())
                action.setVisible(False)
                current_menu = submenu

            for i in range(start_skip, len(key) + 1):
                if i < len(key):
                    menu_name = prefixes.get((domain, key[:i]), 'group').title()
                    current_menu = self.get_or_create_submenu(current_menu, menu_name)
                else:
                    action = Action(domain, key, callback, name)
                    self.addAction(action)
                    current_menu.addAction(action)

    def get_submenu(self, menu, title):
        for a in menu.actions():
            if a.menu():
                if a.menu().title() == title:
                    return a.menu()

    def get_subaction(self, menu, title):
        for a in menu.actions():
            if a.menu():
                if a.menu().title() == title:
                    return a

    def get_or_create_submenu(self, menu, title):
        submenu = self.get_submenu(menu, title)
        if submenu is None:
            submenu = QtWidgets.QMenu(title, self)
            menu.addMenu(submenu)

        return submenu

    # def event(self, event):
    #     if event.type() == QtCore.QEvent.KeyPress:
    #         print("Press: ", event.key(), int(event.modifiers()), event.text())
    #     elif event.type() == QtCore.QEvent.KeyRelease:
    #         print("Release: ", event.key(), int(event.modifiers()),
    #               event.text())

    #     return super().event(event)

    #     # if isinstance(event, (QtGui.QEnterEvent, QtGui.QHoverEvent)):
    #     #     return True

    #     # if (event.type() is QtCore.QEvent.Type.Leave) or (
    #     #         event.type() is QtCore.QEvent.Type.Enter) or (
    #     #             event.type() is QtCore.QEvent.Type.HoverMove):
    #     #     editor = reg['gearbox/editor']
    #     #     graph = reg['gearbox/graph']
    #     #     graph.clearFocus()
    #     #     editor.win.widget.activateWindow()
    #     #     editor.win.widget.setFocus()
    #     #     print(f'Set focus')

    #     print(f'Event: {event.type()}')

    #     return super().event(event)
    # def keyPressEvent(self, event):
    #     print(f"Press event: {event.key()} + {event.modifiers()} => {event.text()}")
    #     return super().keyPressEvent(event)

    def add_shortcut(self, shortcut):
        self.shortcuts.append(shortcut)
        shortcut.activated.connect(partial(self.shortcut_trigger, shortcut))

    def shortcut_trigger(self, shortcut):
        self.shortcut_triggered.emit(shortcut)

    def _init_actions(self):
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_G),
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

    def remove_buffer(self, widget):
        self.buffers.remove(widget)

    def _key_cancel_event(self):
        self.key_cancel.emit()

    def shortcut_prefix(self):
        print("Ambiguous shortcut!")

    def change_domain(self, domain):

        current_menu = self.menuBar()
        prev_domain = reg['gearbox/domain']

        if prev_domain:
            action = self.get_subaction(current_menu, reg['gearbox/domain'].title())
            if action:
                action.setVisible(False)

        reg['gearbox/domain'] = domain

        if domain:
            action = self.get_subaction(current_menu, domain.title())
            if action:
                action.setVisible(True)

        self.domain_changed.emit(domain)


class MainWindowPlugin(PluginBase):
    @classmethod
    def bind(cls):
        reg['gearbox/shortcuts'] = []
        reg['gearbox/prefixes'] = {}

        @inject
        def menu_visibility(var, visible, main=MayInject('gearbox/main/inst')):
            if main:
                main.menuBar().setVisible(visible)

        reg.confdef('gearbox/main/menus', default=True, setter=menu_visibility)
