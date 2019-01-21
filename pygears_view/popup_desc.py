from PySide2 import QtWidgets, QtCore, QtGui
from pygears.conf import Inject, reg_inject, bind, MayInject
from .html_utils import HtmlFormatter
from .layout import active_buffer


# class PopupDesc(QtWidgets.QLabel):
class PopupDesc(QtWidgets.QTextEdit):
    @reg_inject
    def __init__(self,
                 max_width=500,
                 max_height=500,
                 main=Inject('viewer/main')):
        super().__init__()
        self.setParent(main)
        self.max_width = max_width
        self.buff = None
        # self.max_height = max_height
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        main.key_cancel.connect(self.cancel)
        self.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.timeout_timer = QtCore.QTimer()
        self.timeout_timer.timeout.connect(self.cancel)
        self.timeout_timer.setSingleShot(True)

        self.delay_timer = QtCore.QTimer()
        self.delay_timer.timeout.connect(self.show)
        self.delay_timer.setSingleShot(True)
        self.document().setDefaultStyleSheet(
            HtmlFormatter().get_style_defs('.highlight') +
            '\n.highlight  { background: rgba(255, 255, 255, 0);}')
        self.setReadOnly(True)

        self.setStyleSheet("""
        border: 2px solid rgba(170, 140, 0, 255);
        background-color: rgba(255, 255, 255, 150);
        inset grey;
        """)

    @reg_inject
    def reposition(self):
        win = self.buff.view
        self.move(win.x() + win.width() - self.width(), win.y())

    def show(self):
        super().show()
        self.update()
        self.document().adjustSize()
        content_width = (self.document().idealWidth() + 10 +
                         self.contentsMargins().left() * 2)
        content_height = (
            self.document().size().height() + self.contentsMargins().top() * 2)

        # self.setMinimumHeight(min(content_height, self.max_height))
        self.setMinimumHeight(content_height)

        # print(content_width)
        if content_width < self.max_width:
            self.setMinimumWidth(content_width)

        self.reposition()
        self.delay_timer.stop()

    def popup(self, text, buff=None, delay=1000, timeout=None):
        if buff is None:
            buff = active_buffer()

        if self.buff is not None:
            self.buff.view.resized.disconnect(self.reposition)

        self.buff = buff
        self.buff.view.resized.connect(self.reposition)

        if timeout:
            self.timeout_timer.setInterval(timeout)
            self.timeout_timer.start()

        self.setMinimumHeight(100)
        self.setMinimumWidth(300)
        self.setText(text)
        self.adjustSize()

        if delay and not self.isVisible():
            self.delay_timer.setInterval(delay)
            self.delay_timer.start()
        else:
            self.show()

    def cancel(self):
        self.hide()
        self.timeout_timer.stop()
        self.delay_timer.stop()


@reg_inject
def popup_desc(text, w=MayInject('viewer/popup_desc')):
    if w is None:
        w = PopupDesc()
        bind('viewer/popup_desc', w)

    w.popup(text)
