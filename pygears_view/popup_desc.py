from PySide2 import QtWidgets, QtCore
from pygears.conf import Inject, reg_inject, bind, MayInject


class PopupDesc(QtWidgets.QLabel):
    @reg_inject
    def __init__(self, main=Inject('viewer/main')):
        super().__init__()
        self.setParent(main)
        self.setMaximumWidth(500)
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)
        self.setAlignment(QtCore.Qt.AlignTop)
        main.key_cancel.connect(self.cancel)
        main.resized.connect(self.reposition)
        self.setWordWrap(True)
        self.timeout_timer = QtCore.QTimer()
        self.timeout_timer.timeout.connect(self.cancel)
        self.timeout_timer.setSingleShot(True)

        self.delay_timer = QtCore.QTimer()
        self.delay_timer.timeout.connect(self.show)
        self.delay_timer.setSingleShot(True)

        self.setStyleSheet("""
        border: 2px solid rgba(170, 140, 0, 255);
        background-color: rgba(255, 255, 255, 150);
        inset grey;
        """)

    @reg_inject
    def reposition(self, main=Inject('viewer/main')):
        self.move(main.width() - self.width(), 0)

    def show(self):
        super().show()
        self.update()
        self.reposition()
        self.delay_timer.stop()

    def popup(self, text, delay=1000, timeout=None):
        if timeout:
            self.timeout_timer.setInterval(timeout)
            self.timeout_timer.start()

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
