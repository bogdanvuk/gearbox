import os
from PySide2 import QtWidgets, QtCore
from .stylesheet import STYLE_MINIBUFFER, STYLE_TABSEARCH_LIST
from pygears.conf import Inject, reg_inject


class Minibuffer(QtCore.QObject):
    completed = QtCore.Signal(object)
    filled = QtCore.Signal(str)
    start = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.view = QtWidgets.QHBoxLayout()
        self.msgLabel = QtWidgets.QLabel()
        self.input_box = InputBox()
        self.view.addWidget(self.msgLabel)
        self.view.addWidget(self.input_box)
        self.view.setSpacing(0)
        self.view.setContentsMargins(0, 0, 0, 0)

        self.msgLabel.setStyleSheet(STYLE_MINIBUFFER)
        self.msgLabel.setMargin(0)
        self.msgLabel.setVisible(False)

        self.input_box.tab_key_event.connect(self.tab_key_event)
        self.input_box.cancel.connect(self.cancel)
        self.input_box.textEdited.connect(self._singled_out)
        self.input_box.returnPressed.connect(self._on_search_submitted)

        self.timer = QtCore.QTimer()
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self.message_cleanup)
        self.timer.setSingleShot(True)

    def message(self, message):
        self.timer.stop()
        self.msgLabel.setText(message)
        self.msgLabel.show()
        self.timer.start()

    def complete_cont(self, message=None, completer=None, text=''):
        try:
            self.filled.disconnect()
        except (TypeError, RuntimeError):
            pass

        if message:
            self.msgLabel.setMaximumWidth(self.msgLabel.parentWidget().width())
            self.msgLabel.setText(message)
            self.msgLabel.adjustSize()
            # QLabel commes with a padding that is hard to remove, so two
            # pixels are removed by hand
            self.msgLabel.setMaximumWidth(self.msgLabel.width() - 2)
            self.msgLabel.show()
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

        self.timer.stop()
        self.start.emit()

        self.complete_cont(message, completer)

        if self._completer:
            self._completer.complete()

    def _singled_out(self, text):
        if not self._completer:
            return

        self._completer.setCompletionPrefix(text)

        if (self._completer.completionCount() == 1):
            completion_text = self._completer.currentCompletion()
            if (len(completion_text) >= len(text)) and (len(text) >
                                                        self.prev_text_len):
                self.input_box.setText(completion_text)

        self.prev_text_len = len(text)

    def cancel(self):
        if self.input_box.isEnabled():
            self.cleanup(None)

    @reg_inject
    def cleanup(self, result, main=Inject('viewer/main')):
        self.completed.emit(result)
        main.change_domain(self.previous_domain)
        self.input_box.setText('')
        self.input_box.setDisabled(True)
        self.input_box.parentWidget().clearFocus()

        self.message_cleanup()

    def message_cleanup(self):
        self.msgLabel.setVisible(False)

    def _on_search_submitted(self, index=0):
        if self._completer and hasattr(self._completer, 'get_result'):
            result = self._completer.get_result(self.input_box.text())
        else:
            result = self.input_box.text()

        self.cleanup(result)

    def completions(self):
        cur_row = self._completer.currentRow()
        for i in range(self._completer.completionCount()):
            self._completer.setCurrentRow(i)
            yield self._completer.currentCompletion()

        self._completer.setCurrentRow(cur_row)

    def tab_key_event(self):
        prefix = os.path.commonprefix(list(self.completions()))
        self.input_box.setText(prefix)
        if (self._completer.completionCount() == 1):
            self.filled.emit(prefix)


class InputBox(QtWidgets.QLineEdit):

    tab_key_event = QtCore.Signal()
    cancel = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_MacShowFocusRect, 0)
        self.setStyleSheet(STYLE_MINIBUFFER)
        self.setDisabled(True)
        # self.hide()

    def focusOutEvent(self, event):
        self.cancel.emit()
        super().focusOutEvent(event)

    def event(self, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if (event.key() == QtCore.Qt.Key_Tab
                    and event.modifiers() == QtCore.Qt.NoModifier):
                self.tab_key_event.emit()
                return False
            elif (event.key() == QtCore.Qt.Key_J
                  and event.modifiers() == QtCore.Qt.ControlModifier):
                if self.completer():
                    completer = self.completer()
                    popup = completer.popup()
                    row = popup.currentIndex().row()
                    if row < completer.completionCount() - 1:
                        popup.setCurrentIndex(
                            completer.completionModel().index(row + 1, 0))
            elif (event.key() == QtCore.Qt.Key_K
                  and event.modifiers() == QtCore.Qt.ControlModifier):
                if self.completer():
                    completer = self.completer()
                    popup = completer.popup()
                    row = popup.currentIndex().row()
                    if row != 0:
                        popup.setCurrentIndex(
                            completer.completionModel().index(abs(row) - 1, 0))
            elif (event.key() == QtCore.Qt.Key_G
                  and event.modifiers() == QtCore.Qt.ControlModifier):
                self.cancel.emit()

        return super().event(event)
