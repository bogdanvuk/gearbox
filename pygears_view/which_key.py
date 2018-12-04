from PySide2.QtWidgets import QLabel
from .stylesheet import STYLE_WHICH_KEY
from pygears.conf import Inject, bind, reg_inject
from PySide2.QtGui import QKeySequence


@reg_inject
def which_key(main=Inject('viewer/main')):
    w = WhichKey(main)
    main.vbox.insertWidget(1, w)
    bind('viewer/which_key', w)


class WhichKey(QLabel):
    @reg_inject
    def __init__(self, parent=None, main=Inject('viewer/main')):
        super().__init__(parent)
        self.setStyleSheet(STYLE_WHICH_KEY)
        self.setMargin(2)
        self.hide()

        main.key_cancel.connect(self.cancel)

    @reg_inject
    def show(self, main=Inject('viewer/main')):
        which_key_string = []
        for s in main.shortcuts:
            if not s.enabled:
                continue

            keys = QKeySequence(s.key).toString().split('+')

            try:
                shift_id = keys.index('Shift')
                keys.pop(shift_id)
            except ValueError:
                shift_id = None

            try:
                ctrl_id = keys.index('Ctrl')
                keys.pop(ctrl_id)
            except ValueError:
                ctrl_id = None

            if shift_id is None:
                keys[0] = keys[0].lower()

            if ctrl_id is not None:
                keys.insert(0, 'C')

            shortut_string = (f'<font color=\"darkorchid\"><b>'
                              f'{"-".join(keys)}'
                              f'</b></font> &#8594; {s.callback.__name__}')

            which_key_string.append(shortut_string)

        self.setText('&nbsp;&nbsp;'.join(which_key_string))
        super().show()

    def cancel(self):
        self.hide()
