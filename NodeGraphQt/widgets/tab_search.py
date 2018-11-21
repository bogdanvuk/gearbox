#!/usr/bin/python
import os
from PySide2 import QtCore, QtWidgets

from pygears.conf import Inject, reg_inject
from NodeGraphQt.widgets.stylesheet import STYLE_TABSEARCH, STYLE_TABSEARCH_LIST

from pygears.core.hier_node import HierVisitorBase


class TreeItem(object):
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return len(self.itemData)

    def data(self, column):
        try:
            return self.itemData[column]
        except IndexError:
            return None

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)

        return 0

    def __repr__(self):
        return 'TreeItem(%s)' % self.itemData


class TreeModel(QtCore.QAbstractItemModel):
    def __init__(self, root, parent=None):
        super(TreeModel, self).__init__(parent)

        self.rootItem = TreeItem(("Gear", root))
        self.setupModelData(root, self.rootItem)

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        if role == QtCore.Qt.EditRole:
            return self.rootItem.data(0)

        if role != QtCore.Qt.DisplayRole:
            return None

        item = index.internalPointer()

        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.rootItem.data(section)

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def setupModelData(self, root, parent):
        v = Visitor(parent)
        v.visit(root)


class Visitor(HierVisitorBase):
    def __init__(self, parent):
        self.parents = [parent]

    def Gear(self, node):
        tree_item = TreeItem((node.basename, node), self.parents[-1])
        self.parents[-1].appendChild(tree_item)

        self.parents.append(tree_item)
        super().HierNode(node)
        self.parents.pop()

        return True


class TabSearchCompleter(QtWidgets.QCompleter):
    """
    QCompleter adapted from:
    https://stackoverflow.com/questions/5129211/qcompleter-custom-completion-rules
    """
    search_submitted = QtCore.Signal(str)

    def __init__(self, nodes=None, parent=None):
        super(TabSearchCompleter, self).__init__(nodes, parent)
        self.setCompletionMode(self.PopupCompletion)
        self.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._local_completion_prefix = ''
        self._using_orig_model = False
        self._source_model = None
        self._filter_model = None

    # def splitPath(self, path):
    #     self._local_completion_prefix = path
    #     self.updateModel()
    #     if self._filter_model.rowCount() == 0:
    #         self._using_orig_model = False
    #         self._filter_model.setSourceModel(QtCore.QStringListModel([path]))
    #         return [path]
    #     return []

    def splitPath(self, path):
        return path.split('/')

    def pathFromIndex(self, index):
        result = []
        while index.isValid():
            result = [self.model().data(index, QtCore.Qt.DisplayRole)] + result
            index = index.parent()
        r = '/'.join(result)
        return r

    def updateModel(self):
        if not self._using_orig_model:
            self._filter_model.setSourceModel(self._source_model)

        pattern = QtCore.QRegExp(self._local_completion_prefix,
                                 QtCore.Qt.CaseInsensitive,
                                 QtCore.QRegExp.FixedString)
        self._filter_model.setFilterRegExp(pattern)

    # def setModel(self, model):
    #     self._source_model = model
    #     self._filter_model = QtCore.QSortFilterProxyModel(self)
    #     self._filter_model.setSourceModel(self._source_model)
    #     super(TabSearchCompleter, self).setModel(self._filter_model)
    #     self.popup().setStyleSheet(STYLE_TABSEARCH_LIST)
    #     self._using_orig_model = True


class TabSearchWidget(QtWidgets.QLineEdit):

    search_submitted = QtCore.Signal(str)

    def __init__(self, parent=None, node_dict=None):
        super(TabSearchWidget, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_MacShowFocusRect, 0)
        self.setStyleSheet(STYLE_TABSEARCH)
        self.setMinimumSize(200, 22)
        self.setTextMargins(2, 0, 2, 0)
        self.hide()

        self._node_dict = node_dict or {}

        node_names = sorted(self._node_dict.keys())
        self._model = QtCore.QStringListModel(node_names, self)

        self._completer = TabSearchCompleter()
        self._completer.setModel(self._model)
        self.setCompleter(self._completer)

        popup = self._completer.popup()
        popup.clicked.connect(self._on_search_submitted)
        self.returnPressed.connect(self._on_search_submitted)
        self.textChanged.connect(self._singled_out)
        self.prev_text_len = len(self.text())

    def _singled_out(self, text):
        if (self._completer.completionCount() == 1):
            completion_text = self._completer.currentCompletion()
            if (len(completion_text) > len(text)) and (len(text) >
                                                       self.prev_text_len):

                model = self._completer.completionModel()
                gear_model_index = model.sibling(
                    self._completer.currentRow(), 1,
                    self._completer.currentIndex())

                gear = model.data(gear_model_index)

                if gear.child:
                    completion_text += '/'

                self.setText(completion_text)

        self.prev_text_len = len(text)

    def completions(self):
        cur_row = self._completer.currentRow()
        for i in range(self._completer.completionCount()):
            self._completer.setCurrentRow(i)
            yield self._completer.currentCompletion()

        self._completer.setCurrentRow(cur_row)

    def event(self, event):
        if event.type() == QtCore.QEvent.KeyPress and event.key(
        ) == QtCore.Qt.Key_Tab:
            prefix = os.path.commonprefix(list(self.completions()))
            self.setText(prefix)
            return False
        return super().event(event)

    def _on_search_submitted(self, index=0):
        print("Here?")

        self.text = self._completer.currentCompletion()

        # node_type = self._node_dict.get(self.text())
        # if node_type:
        #     self.search_submitted.emit(node_type)
        # self.close()
        # self.parentWidget().clearFocus()

    def showEvent(self, event):
        super(TabSearchWidget, self).showEvent(event)
        self.setSelection(0, len(self.text()))
        self.setFocus()
        if not self.text():
            self.completer().popup().show()
            self.completer().complete()

    @reg_inject
    def set_nodes(self, node_dict=None, root=Inject('gear/hier_root')):
        self._node_dict = node_dict or {}

        self._model = TreeModel(root)
        self._completer.setModel(self._model)
        self._completer.setCompletionColumn(0)
        self._completer.setCompletionRole(QtCore.Qt.DisplayRole)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
