from PySide2 import QtCore, QtWidgets, QtGui
from pygears.conf import PluginBase, registry, safe_bind, reg_inject, Inject
from .stylesheet import STYLE_MODELINE, STYLE_MINIBUFFER

from .minibuffer import Minibuffer
from .modeline import Modeline


@reg_inject
def active_buffer(main=Inject('viewer/main')):
    return main.buffers.current


class Shortcut(QtCore.QObject):
    @reg_inject
    def __init__(self, domain, key, callback, main=Inject('viewer/main')):
        if not isinstance(key, tuple):
            key = (key, )

        self._qshortcut = QtWidgets.QShortcut(QtGui.QKeySequence(*key), main)
        # self._qshortcut.activated.connect(callback)
        self._qshortcut.activated.connect(self.activated)
        self._qshortcut.activatedAmbiguously.connect(main.shortcut_prefix)
        # self._qshortcut.setContext(QtCore.Qt.ApplicationShortcut)
        # self._qshortcut.setWhatsThis(callback.__name__)
        main.shortcuts.append(self)
        self.domain = domain
        self.key = key
        self.callback = callback
        main.domain_changed.connect(self.domain_changed)

    def activated(self):
        self._qshortcut.setEnabled(False)
        self.callback()
        self._qshortcut.setEnabled(True)

    @property
    def enabled(self):
        return self._qshortcut.isEnabled()

    def domain_changed(self, domain):
        if (self.domain is None
                and domain[0] != '_') or (self.domain == domain):
            self._qshortcut.setEnabled(True)
        else:
            self._qshortcut.setEnabled(False)


class BufferLayout(QtWidgets.QVBoxLayout):
    def __init__(self, parent, buff=None):
        super().__init__()
        self.buff = buff
        self.parent = parent

        self.setSpacing(0)
        self.setMargin(0)
        self.setContentsMargins(0, 0, 0, 0)

        self.modeline = Modeline(self)

        if buff is not None:
            self.addWidget(self.buff)
        else:
            placeholder = QtWidgets.QLabel()
            placeholder.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
            placeholder.setStyleSheet(STYLE_MINIBUFFER)
            self.addWidget(placeholder, 2)

        self.addWidget(self.modeline)

    def split_horizontally(self):
        self.parent.split_horizontally(self)

    def get_window(self, position):
        return self

    def activate(self):
        if self.buff:
            self.buff.activate(self)

        self.modeline.update()

    def place_buffer(self, buff, position):
        self.buff = buff
        self.replaceWidget(self.itemAt(0).widget(), buff.view)

    @property
    @reg_inject
    def active(self, layout=Inject('viewer/layout')):
        return layout.current_window is self

    @property
    def win_num(self):
        return 1

    @property
    def win_id(self):
        return self.parent.child_win_id(self)

    @property
    def position(self):
        return self.parent.child_position(self)

    @property
    def current(self):
        if self.buff.view.hasFocus():
            return self
        else:
            return None


class WindowLayout(QtWidgets.QBoxLayout):
    def __init__(self, parent, size, position, direction=None):
        if direction is None:
            direction = QtWidgets.QBoxLayout.LeftToRight

        self.direction = direction
        self.parent = parent

        super().__init__(direction)

        self.setSpacing(0)
        self.setMargin(0)
        self.setContentsMargins(0, 0, 0, 0)

        self.size = size

        for i in range(size):
            self.addLayout(BufferLayout(self), 1)

    @property
    def current(self):
        for i in range(self.size):
            ret = self.itemAt(i).layout().current
            if ret:
                return ret

    @property
    def position(self):
        return self.parent.child_position(self)

    def child_win_id(self, child):
        win_id = self.parent.child_win_id(self)

        for i in range(self.child_index(child)):
            win_id += self.child(i).win_num

        return win_id

    @property
    def win_num(self):
        win_cnt = 0
        for i in range(self.size):
            win_cnt += self.child(i).win_num()

        return win_cnt

    def child_position(self, child):
        return self.position + (self.child_index(child))

    def child(self, index):
        return self.itemAt(index).layout()

    def child_index(self, child):
        for i in range(self.size):
            if self.itemAt(i).layout() is child:
                return i

    def split_horizontally(self, child):
        pos = self.child_index(child)
        self.size += 1
        self.insertLayout(pos + 1, BufferLayout(self), 1)
        self.child(pos+1).modeline.update()

    def get_window(self, position):
        return self.child(position[0]).get_window(position[1:])

    def place_buffer(self, buff, position):
        self.get_window(position).place_buffer(buff, [])


class BufferStack(QtWidgets.QStackedLayout):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.current_layout_widget = QtWidgets.QWidget()
        self.current_window = None

        safe_bind('viewer/layout', self)

        # layout = WindowLayout(size=1)
        self.current_layout = WindowLayout(self, 1, position=tuple())
        self.current_layout_widget.setLayout(self.current_layout)
        self.addWidget(self.current_layout_widget)

        self.main = main
        self.setMargin(0)
        self.setContentsMargins(0, 0, 0, 0)
        self._buffers = {}
        self.currentChanged.connect(self.current_changed)

    def child_win_id(self, child):
        return 1

    def child_position(self, child):
        return tuple()

    def place_buffer(self, buf, position):
        buf.position = position
        self.current_layout.place_buffer(buf, position)
        self.activate_window(position)

    def get_window(self, position):
        return self.current_layout.get_window(position)

    def active_window(self):
        return self.current_layout.current

    def activate_window(self, position):
        win = self.get_window(position)
        self.current_window = win
        win.activate()
        self.main.change_domain(win.buff.domain)

    def add(self, buf):
        self._buffers[buf.name] = buf
        self.place_buffer(buf, [0])

        # self.addWidget(buf.view)

    def __getitem__(self, key):
        return self._buffers[key]

    def current_changed(self):
        self.main.modeline.setText(self.current.name)
        if hasattr(self.current, 'activate'):
            self.current.activate()

        self.main.change_domain(self.current.domain)

    @property
    def current(self):
        return self.current_layout.current
        # try:
        #     # return list(self._buffers.values())[self.currentIndex()]
        #     return list(self._buffers.values())[0]
        # except KeyError:
        #     return None

    @property
    def current_name(self):
        return list(self._buffers.keys())[0]

    def next_buffer(self):
        next_id = self.currentIndex() + 1
        if next_id >= len(self._buffers):
            self.setCurrentIndex(0)
        else:
            self.setCurrentIndex(next_id)

        self.main.change_domain(self.current_name)


class MainWindow(QtWidgets.QMainWindow):

    key_cancel = QtCore.Signal()
    domain_changed = QtCore.Signal(str)

    def __init__(self, sim_pipe=None, parent=None):
        super().__init__(parent)
        safe_bind('viewer/main', self)

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

        self.buffers = BufferStack(main=self)
        self.vbox.addLayout(self.buffers)

        mainWidget = QtWidgets.QWidget()
        mainWidget.setLayout(self.vbox)
        mainWidget.setContentsMargins(0, 0, 0, 0)

        self.minibuffer = Minibuffer()
        # self.minibuffer.completed.connect(self._minibuffer_completed)
        safe_bind('viewer/minibuffer', self.minibuffer)
        self.vbox.addLayout(self.minibuffer.view)

        self.setCentralWidget(mainWidget)

        self._init_actions()
        self._nodes = []

        for domain, key, callback in registry('viewer/shortcuts'):
            Shortcut(domain, key, callback)

    def _init_actions(self):
        QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_G),
            self).activated.connect(self._key_cancel_event)

    def add_buffer(self, widget):
        self.buffers.add(widget)

    def _key_cancel_event(self):
        self.key_cancel.emit()

    def shortcut_prefix(self):
        print("Prefix!")

    def change_domain(self, domain):
        self.domain_changed.emit(domain)


class MainWindowPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('viewer/shortcuts', [])
