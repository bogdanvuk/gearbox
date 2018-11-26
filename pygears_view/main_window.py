from PySide2 import QtCore, QtWidgets, QtGui
from pygears.conf import PluginBase, registry, safe_bind, reg_inject, Inject

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
    def __init__(self, graph, domain, key, callback):
        self._qshortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key), graph)
        self._qshortcut.activated.connect(callback)
        self._qshortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        self._qshortcut.setWhatsThis(callback.__name__)
        self.domain = domain
        self.key = key
        self.callback = callback
        graph.domain_changed.connect(self.domain_changed)

    @property
    def enabled(self):
        return self._qshortcut.isEnabled()

    def domain_changed(self, domain):
        print(f'{domain} ?= {self.domain}')
        if (self.domain is None) or (self.domain == domain):
            self._qshortcut.setEnabled(True)
        else:
            print('Shortcut disabled')
            self._qshortcut.setEnabled(False)


class BufferStack(QtWidgets.QStackedLayout):
    def __init__(self, graph, parent=None):
        super().__init__(parent)
        self.setMargin(0)
        self.graph = graph
        self.setContentsMargins(0, 0, 0, 0)
        self._buffers = {}

    def __setitem__(self, key, value):
        self._buffers[key] = value
        self.addWidget(value)
        # value.installEventFilter(self.graph)

    def __getitem__(self, key):
        return self._buffers[key]

    @property
    def current_name(self):
        return list(self._buffers.keys())[self.currentIndex()]

    def next_buffer(self):
        next_id = self.currentIndex() + 1
        if next_id >= len(self._buffers):
            self.setCurrentIndex(0)
        else:
            self.setCurrentIndex(next_id)

        self.graph.domain_changed.emit(self.current_name)


class MainWindow(QtWidgets.QMainWindow):

    key_cancel = QtCore.Signal()
    domain_changed = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        safe_bind('viewer/main', self)

        self._undo_stack = QtWidgets.QUndoStack(self)
        self.buffers = {}

        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setSpacing(0)
        self.vbox.setMargin(0)
        self.vbox.setContentsMargins(0, 0, 0, 0)

        self.buffers = BufferStack(graph=self)
        self.vbox.addLayout(self.buffers)

        mainWidget = QtWidgets.QWidget()
        mainWidget.setLayout(self.vbox)
        mainWidget.setContentsMargins(0, 0, 0, 0)

        self.minibuffer = Minibuffer()
        self.minibuffer.completed.connect(self._minibuffer_completed)
        safe_bind('viewer/minibuffer', self.minibuffer)

        self.vbox.addWidget(self.minibuffer)

        self.setCentralWidget(mainWidget)

        self._init_actions()
        self._nodes = []

        self.shortcuts = [
            Shortcut(self, domain, key, callback)
            for domain, key, callback in registry('viewer/shortcuts')
        ]

    def _init_actions(self):
        QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_G),
            self).activated.connect(self._key_cancel_event)

    def _key_cancel_event(self):
        self.key_cancel.emit()

    @reg_inject
    def _minibuffer_completed(self, text, graph=Inject('viewer/graph')):
        try:
            node_path = find_node_by_path(self.top, text)
            for node in node_path[:-1]:
                node.expand()
        except:
            for node in self.selected_nodes():
                node.setSelected(False)
            return

        for node in self.selected_nodes():
            node.setSelected(False)

        node_path[-1].setSelected(True)
        self._viewer.ensureVisible(node_path[-1])


class MainWindowPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('viewer/shortcuts', [])
