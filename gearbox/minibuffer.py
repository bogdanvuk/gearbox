import os
from PySide2 import QtWidgets, QtCore
from .layout import active_buffer
from pygears.conf import Inject, inject


class CompleterItemDelegate(QtWidgets.QItemDelegate):
    # based on https://stackoverflow.com/a/8036666/1504082
    # http://doc.qt.nokia.com/4.7/qitemdelegate.html#drawDisplay
    # http://doc.qt.nokia.com/4.7/qwidget.html#render
    margin_x = 5
    margin_y = 3

    def drawDisplay(self, painter, option, rect, text):
        label = self.make_label(option, text)
        # calculate render anchor point
        point = rect.topLeft()
        point.setX(point.x() + self.margin_x)
        point.setY(point.y() + self.margin_y)

        label.render(
            painter, point, renderFlags=QtWidgets.QWidget.DrawChildren)

    def sizeHint(self, option, index):
        # get text using model and index
        text = index.model().data(index)
        label = self.make_label(option, text)
        return QtCore.QSize(label.width(), label.height() + self.margin_y)

    def setup_label(self, label):
        pass

    def make_label(self, option, text):
        label = QtWidgets.QLabel(text)

        self.setup_label(label)

        # adjust width according to widget's target width
        label.setMinimumWidth(self.target_width - (2 * self.margin_x))
        label.setMaximumWidth(self.target_width - self.margin_x)
        label.setWordWrap(True)
        label.adjustSize()
        return label


class Minibuffer(QtCore.QObject):
    completed = QtCore.Signal(object)
    filled = QtCore.Signal(str)
    start = QtCore.Signal()

    @inject
    def __init__(self, main=Inject('gearbox/main/inst')):
        super().__init__()
        self.view = QtWidgets.QHBoxLayout()

        self.msgLabel = QtWidgets.QLabel()
        self.msgLabel.setAccessibleName("minibuffer-message")
        self.msgLabel.setVisible(False)

        self.input_box = InputBox()
        self.input_box.tab_key_event.connect(self.tab_key_event)
        self.input_box.cancel.connect(self.cancel)
        self.input_box.textEdited.connect(self._singled_out)
        self.input_box.returnPressed.connect(self._on_search_submitted)

        self.view.addWidget(self.msgLabel)
        self.view.addWidget(self.input_box)
        self.view.setSpacing(0)
        self.view.setContentsMargins(0, 0, 0, 0)

        main.key_cancel.connect(self.cancel)

        self.timer = QtCore.QTimer()
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self.message_cleanup)
        self.timer.setSingleShot(True)

    def message(self, message):
        self.timer.stop()
        self._show_message(message)
        self.timer.start()

    def _show_message(self, message):
        self.msgLabel.setMaximumWidth(self.msgLabel.parentWidget().width())
        self.msgLabel.setText(message)
        self.msgLabel.adjustSize()
        # QLabel commes with a padding that is hard to remove, so two
        # pixels are removed by hand
        self.msgLabel.setMaximumWidth(self.msgLabel.width() - 7)
        self.msgLabel.show()
        self.msgLabel.update()

    def complete_cont(self, message=None, completer=None, text=''):
        try:
            self.filled.disconnect()
        except (TypeError, RuntimeError):
            pass

        if message:
            self._show_message(message)
        else:
            self.input_box.setTextMargins(2, 0, 0, 0)

        self.input_box.setText(text)
        self.input_box.setSelection(0, len(self.input_box.text()))
        self.input_box.setFocus()

        self._completer = completer
        if completer:
            self.input_box.setCompleter(self._completer)
            self._completer.popup()
            self.prev_text_len = len(self.input_box.text())
            try:
                self.filled.connect(completer.filled)
            except AttributeError:
                pass

            QtCore.QTimer.singleShot(0.01, self.tab_key_event)

            if hasattr(completer, 'default_completion'):
                default = completer.default_completion
                if default is not None:
                    text = default

        self.start.emit()

    @inject
    def complete(self,
                 message=None,
                 completer=None,
                 main=Inject('gearbox/main/inst'),
                 domain=Inject('gearbox/domain')):
        self.previous_domain = domain
        main.change_domain('minibuffer')
        self.input_box.setDisabled(False)

        self.timer.stop()

        self.complete_cont(message, completer)

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

    @inject
    def cleanup(self, result, main=Inject('gearbox/main/inst')):
        self.completed.emit(result)
        main.change_domain(self.previous_domain)
        self.input_box.setText('')
        self.input_box.setDisabled(True)
        self.input_box.parentWidget().clearFocus()
        if active_buffer():
            active_buffer().activate()

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

        if not self._completer:
            return

        if (self._completer.completionCount() == 1):
            self.filled.emit(prefix)
        else:
            self._completer.setCompletionPrefix(prefix)
            self._completer.complete()


class InputBox(QtWidgets.QLineEdit):

    tab_key_event = QtCore.Signal()
    cancel = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_MacShowFocusRect, 0)
        # self.setStyleSheet(themify(STYLE_MINIBUFFER))
        self.setDisabled(True)
        # self.setFocusPolicy(QtCore.Qt.ClickFocus)
        # self.hide()

    def focusOutEvent(self, event):
        if event.reason() != QtCore.Qt.FocusReason.PopupFocusReason:
            self.cancel.emit()

        super().focusOutEvent(event)

    def event(self, event):

        # if (event.type() in [
        #         QtCore.QEvent.KeyRelease, QtCore.QEvent.ShortcutOverride
        # ]):
        #     if (event.key() == QtCore.Qt.Key_Tab
        #             and event.modifiers() == QtCore.Qt.NoModifier):
        #         print(f'Tab other')
        #         return True

        if event.type() == QtCore.QEvent.ShortcutOverride:
            # print(f'InputBox event: {event.type()}')
            event.ignore()
            return True

        if event.type() == QtCore.QEvent.KeyPress:
            if (event.key() == QtCore.Qt.Key_Tab
                    and event.modifiers() == QtCore.Qt.NoModifier):
                self.tab_key_event.emit()
                return True
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
