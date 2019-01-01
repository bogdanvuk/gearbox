from PySide2 import QtCore, QtWidgets


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
    def __init__(self, nodes=None, parent=None):
        super().__init__(nodes, parent)
        self.setCompletionMode(self.PopupCompletion)
        self.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._local_completion_prefix = ''
        self._using_orig_model = False
        self._source_model = None
        self._filter_model = None

    def splitPath(self, path):
        print(f"splitPath: {path}")
        return path.split('/')

    def pathFromIndex(self, index):
        result = []
        while index.isValid():
            result = [self.model().data(index, QtCore.Qt.DisplayRole)] + result
            index = index.parent()
        r = '/'.join(result)
        return r


def node_search_completer(top):
    completer = NodeSearchCompleter()
    completer.setModel(TreeModel(top))
    completer.setCompletionColumn(0)
    completer.setCompletionRole(QtCore.Qt.DisplayRole)
    completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

    return completer
