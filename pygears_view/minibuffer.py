import os
from PySide2 import QtWidgets, QtCore
from .stylesheet import STYLE_MINIBUFFER, STYLE_TABSEARCH_LIST
from pygears.conf import Inject, reg_inject


class Minibuffer(QtCore.QObject):
    completed = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.view = QtWidgets.QHBoxLayout()
        self.message = QtWidgets.QLabel()
        self.input_box = InputBox()
        self.view.addWidget(self.message)
        self.view.addWidget(self.input_box)

        self.message.setStyleSheet(STYLE_MINIBUFFER)
        self.message.setVisible(False)

        self.input_box.editingFinished.connect(self._on_search_submitted)

    @reg_inject
    def complete(self, message=None, completer=None, main=Inject('viewer/main')):
        self.previous_domain = main.buffers.current_name
        main.change_domain('minibuffer')
        self.input_box.setDisabled(False)

        if message:
            self.message.setText(message)
            self.message.setVisible(True)

        self._completer = completer
        if completer:
            self.input_box.textChanged.connect(self._singled_out)
            self.input_box.setCompleter(self._completer)
            popup = self._completer.popup()
            popup.setStyleSheet(STYLE_TABSEARCH_LIST)
            self.prev_text_len = len(self.input_box.text())

        self.input_box.setSelection(0, len(self.input_box.text()))
        self.input_box.setFocus()

        if completer:
            self._completer.popup().show()
            self._completer.complete()

    def _singled_out(self, text):
        print(f"Singled out: {text}")
        print(f"Completions count: {self._completer.completionCount()}")
        if (self._completer.completionCount() == 1):
            completion_text = self._completer.currentCompletion()
            print(f"Completion text: {completion_text}")
            if (len(completion_text) > len(text)) and (len(text) >
                                                       self.prev_text_len):
                list_index = self._completer.currentIndex()
                index = self._completer.completionModel().mapToSource(
                    list_index)

                if index.model().hasChildren(index):
                    completion_text += '/'

                self.input_box.setText(completion_text)

        self.prev_text_len = len(text)

    @reg_inject
    def _on_search_submitted(self, index=0, main=Inject('viewer/main')):
        if self.input_box.text():
            self.completed.emit(self.input_box.text())
            main.change_domain(self.previous_domain)
            self.input_box.setText('')
            self.input_box.setDisabled(True)
            self.input_box.parentWidget().clearFocus()

        self.message.setVisible(False)

    def completions(self):
        cur_row = self._completer.currentRow()
        for i in range(self._completer.completionCount()):
            self._completer.setCurrentRow(i)
            yield self._completer.currentCompletion()

        self._completer.setCurrentRow(cur_row)

    def tab_key_event(self):
        prefix = os.path.commonprefix(list(self.completions()))
        self.input_box.setText(prefix)


class InputBox(QtWidgets.QLineEdit):

    completed = QtCore.Signal(str)
    tab_key_event = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_MacShowFocusRect, 0)
        self.setStyleSheet(STYLE_MINIBUFFER)
        self.setTextMargins(2, 0, 2, 0)
        self.setDisabled(True)
        # self.hide()

    def event(self, event):
        if (event.type() == QtCore.QEvent.KeyPress
                and event.key() == QtCore.Qt.Key_Tab
                and event.modifiers() == QtCore.Qt.NoModifier):
            self.tab_key_event.emit()
            return False
        return super().event(event)
