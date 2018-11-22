import os
from PySide2 import QtWidgets, QtCore
from .stylesheet import STYLE_MINIBUFFER, STYLE_TABSEARCH_LIST
from .tab_search import TabSearchCompleter, TreeModel
from pygears.conf import Inject, reg_inject


class Minibuffer(QtWidgets.QLineEdit):

    completed = QtCore.Signal(str)

    def __init__(self, parent=None, node_dict=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_MacShowFocusRect, 0)
        self.setStyleSheet(STYLE_MINIBUFFER)
        self.setTextMargins(2, 0, 2, 0)
        self.setDisabled(True)
        # self.hide()

    @reg_inject
    def complete(self, root=Inject('gear/hier_root')):
        self.setDisabled(False)
        self._completer = TabSearchCompleter()
        self._model = TreeModel(root)
        self._completer.setModel(self._model)
        self._completer.setCompletionColumn(0)
        self._completer.setCompletionRole(QtCore.Qt.DisplayRole)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.setCompleter(self._completer)
        popup = self._completer.popup()
        popup.setStyleSheet(STYLE_TABSEARCH_LIST)
        self.editingFinished.connect(self._on_search_submitted)
        self.textChanged.connect(self._singled_out)
        self.prev_text_len = len(self.text())

        self.setSelection(0, len(self.text()))
        self.setFocus()
        self.completer().popup().show()
        self.completer().complete()

    def _singled_out(self, text):
        if (self._completer.completionCount() == 1):
            completion_text = self._completer.currentCompletion()
            if (len(completion_text) > len(text)) and (len(text) >
                                                       self.prev_text_len):
                list_index = self._completer.currentIndex()
                index = self._completer.completionModel().mapToSource(
                    list_index)

                if self._model.hasChildren(index):
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
        if (event.type() == QtCore.QEvent.KeyPress
                and event.key() == QtCore.Qt.Key_Tab
                and event.modifiers() == QtCore.Qt.NoModifier):
            prefix = os.path.commonprefix(list(self.completions()))
            self.setText(prefix)
            return False
        return super().event(event)

    def _on_search_submitted(self, index=0):
        if self.text():
            print("Done!")
            self.completed.emit(self.text())
            self.setText('')
            self.setDisabled(True)
            self.parentWidget().clearFocus()
