from PySide2 import QtCore, QtWidgets, QtGui
from pygears.conf import Inject, inject
from .html_utils import fontify
from .node_model import NodeModel
from .minibuffer import CompleterItemDelegate


class TaskDelegate(CompleterItemDelegate):
    def __init__(self, node):
        super().__init__()
        self.node = node

    def setup_label(self, label):
        text = label.text()
        try:
            child = self.node[text]

            if isinstance(child, NodeModel):
                if child.hierarchical:
                    label.setStyleSheet(
                        "color: darkorchid; background-color: transparent;")
                else:
                    label.setStyleSheet(
                        "color: lightblue; background-color: transparent;")
            else:
                label.setStyleSheet(
                    "color: gold; background-color: transparent;")

        except KeyError:
            label.setStyleSheet("color: rgba(255, 255, 255, 150)")


class NodeSearchCompleter(QtWidgets.QCompleter):
    def __init__(self, node=None):
        super().__init__()
        self.setup_model(node)

    def setup_model(self, node):
        self.setCompletionMode(self.PopupCompletion)
        self.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.node = node

        model = QtCore.QStringListModel()

        completion_list = [c.basename for c in node.child]
        if node.parent is not None:
            completion_list.extend(['..', '/'])

        model.setStringList(completion_list)

        self.setModel(model)
        self.setCompletionColumn(0)
        self.setCurrentRow(0)

    def complete(self):
        self.delegate = TaskDelegate(self.node)
        self.delegate.target_width = self.popup().width()
        self.popup().setItemDelegate(self.delegate)
        super().complete()

    def setCompletionPrefix(self, prefix):
        if (len(prefix) > 0) and (prefix[-1] == '/'):
            self.filled(prefix[:-1])

        super().setCompletionPrefix(prefix)

    @property
    def default_completion(self):
        if len(self.node.child) == 1:
            return self.node.child[0].basename
        else:
            return None

    def get_result(self, text):
        return self.node[text].name

    @inject
    def filled(self, text, minibuffer=Inject('gearbox/minibuffer')):
        if text == '..':
            node = self.node.parent
        elif text == '/':
            node = self.node.root()
        else:
            node = self.node[text]

        if node.child:
            self.setup_model(node)
            minibuffer.complete_cont(f'{node.name}/', self)


def node_search_completer(top):
    return NodeSearchCompleter(top)
