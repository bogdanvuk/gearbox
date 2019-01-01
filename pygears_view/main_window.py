from PySide2 import QtCore, QtWidgets, QtGui
from pygears.conf import PluginBase, registry, safe_bind, reg_inject, Inject
from .stylesheet import STYLE_MODELINE

from .minibuffer import Minibuffer


def _find_rec(path, root):
    parts = path.split("/")

    # if parts[0] == '..':
    #     return _find_rec("/".join(parts[1:]), root.parent)

    for node in root._nodes:
        child = node.model
        if hasattr(child, 'basename') and child.basename == parts[0]:
            break
    else:
        raise Exception()

    if len(parts) == 1:
        return [node]
    else:
        path_rest = "/".join(parts[1:])
        if path_rest:
            return [node] + _find_rec("/".join(parts[1:]), node)
        else:
            return [node]


def find_node_by_path(root, path):
    return _find_rec(path, root)


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


class BufferStack(QtWidgets.QStackedLayout):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.setMargin(0)
        self.main = main
        self.setContentsMargins(0, 0, 0, 0)
        self._buffers = {}
        self.currentChanged.connect(self.current_changed)

    def __setitem__(self, key, value):
        self._buffers[key] = value
        self.addWidget(value)

    def __getitem__(self, key):
        return self._buffers[key]

    def current_changed(self):
        self.main.modeline.setText(self.current_name)
        if hasattr(self.current, 'activate'):
            self.current.activate()

        self.main.change_domain(self.current_name)

    @property
    def current(self):
        try:
            return list(self._buffers.values())[self.currentIndex()]
        except KeyError:
            return None

    @property
    def current_name(self):
        return list(self._buffers.keys())[self.currentIndex()]

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

        self._undo_stack = QtWidgets.QUndoStack(self)
        self.buffers = {}
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
        self.minibuffer.completed.connect(self._minibuffer_completed)
        safe_bind('viewer/minibuffer', self.minibuffer)

        self.modeline = QtWidgets.QLabel(self)
        self.modeline.setStyleSheet(STYLE_MODELINE)

        safe_bind('viewer/modeline', self.modeline)

        self.vbox.addWidget(self.modeline)
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

    def _key_cancel_event(self):
        self.key_cancel.emit()

    def shortcut_prefix(self):
        print("Prefix!")

    def change_domain(self, domain):
        self.domain_changed.emit(domain)

    @reg_inject
    def _minibuffer_completed(self, text, graph=Inject('viewer/graph')):
        try:
            node_path = find_node_by_path(graph.top, text)
            for node in node_path[:-1]:
                node.expand()
        except:
            for node in graph.selected_nodes():
                node.setSelected(False)
            return

        for node in graph.selected_nodes():
            node.setSelected(False)

        node_path[-1].setSelected(True)
        graph.ensureVisible(node_path[-1])


class MainWindowPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('viewer/shortcuts', [])
