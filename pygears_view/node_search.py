from PySide2 import QtCore, QtWidgets
from pygears.conf import Inject, reg_inject


class TreeModel(QtCore.QAbstractItemModel):
    def __init__(self, root, parent=None):
        super(TreeModel, self).__init__(parent)
        self.root = root

    def columnCount(self, parent):
        return 1

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == QtCore.Qt.EditRole:
            return self.root.basename

        if role != QtCore.Qt.DisplayRole:
            return None

        item = index.internalPointer()

        return item.basename

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if (orientation == QtCore.Qt.Horizontal
                and role == QtCore.Qt.DisplayRole):
            return self.root.basename

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.root
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child[row]
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent

        if parentItem == self.root:
            return QtCore.QModelIndex()

        row = parentItem.parent.child.index(parentItem)

        return self.createIndex(row, 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.root
        else:
            parentItem = parent.internalPointer()

        # print(f"childCount: {parentItem.childCount()}")
        return len(parentItem.child)


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
        self.setCompletionPrefix('')
        self.setCompletionColumn(0)
        self.setCurrentRow(0)

    @property
    def default_completion(self):
        if len(self.node.child) == 1:
            return self.node.child[0].basename
        else:
            return None

    def get_result(self, text):
        return self.node[text].name

    @reg_inject
    def filled(self, text, minibuffer=Inject('viewer/minibuffer')):
        print(f"Try looking for {text} inside {self.node.name}")

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
