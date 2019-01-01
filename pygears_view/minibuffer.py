import os
from PySide2 import QtWidgets, QtCore
from .stylesheet import STYLE_MINIBUFFER, STYLE_TABSEARCH_LIST
from pygears.conf import Inject, reg_inject


class Minibuffer(QtCore.QObject):
    completed = QtCore.Signal(str)
    filled = QtCore.Signal(str)
    start = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.view = QtWidgets.QHBoxLayout()
        self.message = QtWidgets.QLabel()
        self.input_box = InputBox()
        self.view.addWidget(self.message)
        self.view.addWidget(self.input_box)
        self.view.setSpacing(0)
        self.view.setContentsMargins(0, 0, 0, 0)

        self.message.setStyleSheet(STYLE_MINIBUFFER)
        self.message.setMargin(0)
        self.message.setVisible(False)

        self.input_box.tab_key_event.connect(self.tab_key_event)
        self.input_box.textEdited.connect(self._singled_out)
        self.input_box.returnPressed.connect(self._on_search_submitted)

    def complete_cont(self, message=None, completer=None, text=''):
        try:
            self.filled.disconnect()
        except (TypeError, RuntimeError):
            pass

        if message:
            self.message.setMaximumWidth(self.message.parentWidget().width())
            self.message.setText(message)
            self.message.adjustSize()
            # QLabel commes with a padding that is hard to remove, so two
            # pixels are removed by hand
            self.message.setMaximumWidth(self.message.width() - 2)
            self.message.show()
        else:
            self.input_box.setTextMargins(2, 0, 0, 0)

        self._completer = completer
        if completer:
            self.input_box.setCompleter(self._completer)
            # self._completer.setCompletionPrefix(text)
            popup = self._completer.popup()
            popup.setStyleSheet(STYLE_TABSEARCH_LIST)
            self.prev_text_len = len(self.input_box.text())
            try:
                self.filled.connect(completer.filled)
            except AttributeError:
                pass

            if hasattr(completer, 'default_completion'):
                default = completer.default_completion
                if default is not None:
                    text = default

        print(f"starting with text: {text}")
        self.input_box.setText(text)
        self.input_box.setSelection(0, len(self.input_box.text()))
        self.input_box.setFocus()

    @reg_inject
    def complete(self,
                 message=None,
                 completer=None,
                 main=Inject('viewer/main')):
        self.previous_domain = main.buffers.current_name
        main.change_domain('minibuffer')
        self.input_box.setDisabled(False)

        self.complete_cont(message, completer)

        if self._completer:
            self._completer.complete()

    def _singled_out(self, text):
        self._completer.setCompletionPrefix(text)

        if (self._completer.completionCount() == 1):
            completion_text = self._completer.currentCompletion()
            if (len(completion_text) >= len(text)) and (len(text) >
                                                        self.prev_text_len):
                self.input_box.setText(completion_text)
                self.filled.emit(completion_text)

                # Immediatelly show possibly new completer. Need to call
                # complete() async, apparently present events need to resolve
                QtCore.QTimer.singleShot(100, self._completer.complete)

        self.prev_text_len = len(text)

    @reg_inject
    def _on_search_submitted(self, index=0, main=Inject('viewer/main')):
        if self._completer and hasattr(self._completer, 'get_result'):
            result = self._completer.get_result(self.input_box.text())
        else:
            result = self.input_box.text()

        self.completed.emit(result)
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

    tab_key_event = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_MacShowFocusRect, 0)
        self.setStyleSheet(STYLE_MINIBUFFER)
        self.setDisabled(True)
        # self.hide()

    def event(self, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if (event.key() == QtCore.Qt.Key_Tab
                    and event.modifiers() == QtCore.Qt.NoModifier):
                self.tab_key_event.emit()
                return False

        return super().event(event)
