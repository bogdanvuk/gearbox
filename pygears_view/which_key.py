import math
from PySide2.QtWidgets import QLabel
from .stylesheet import STYLE_WHICH_KEY
from pygears.conf import Inject, bind, reg_inject
from PySide2.QtGui import QKeySequence
from PySide2 import QtCore


@reg_inject
def which_key(main=Inject('viewer/main')):
    w = WhichKey(main)
    main.vbox.insertWidget(main.vbox.count() - 1, w)
    bind('viewer/which_key', w)


def html_tabulate(table):
    res = ['<table>']
    for row in table:
        res.append('<tr>')
        for width, elem in row:
            res.append(f'<td width={width}>{elem}</td>')

        res.append('</tr>')

    res.append('<table>')

    return '\n'.join(res)


class WhichKey(QLabel):
    @reg_inject
    def __init__(self, parent=None, main=Inject('viewer/main')):
        super().__init__(parent)
        self.setStyleSheet(STYLE_WHICH_KEY)
        self.setMargin(2)
        self.hide()
        parent.installEventFilter(self)

        main.key_cancel.connect(self.cancel)
        main.domain_changed.connect(self.domain_changed)
        self.prefixes = {}
        self.current_prefix = []

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.ShortcutOverride:
            if event.key() in self.prefixes:
                self.current_prefix.append(event.key())
                self.show()
        elif event.type() == QtCore.QEvent.KeyRelease:
            if self.current_prefix and (event.key() not in self.prefixes):
                self.current_prefix.clear()
                self.hide()

        return super().eventFilter(obj, event)

    @reg_inject
    def domain_changed(self, domain, main=Inject('viewer/main')):
        self.prefixes.clear()
        for s in main.shortcuts:
            if (s.domain is None and domain[0] != '_') or (s.domain == domain):
                if len(s.key) > 1:
                    self.prefixes[s.key[0]] = s

    @reg_inject
    def show(self, main=Inject('viewer/main')):

        which_key_string = {}
        for s in main.shortcuts:
            if not s.enabled:
                continue

            key = s.key

            if self.current_prefix:
                if s.key[0] != self.current_prefix[0]:
                    continue
                else:
                    key = key[1:]

            if len(key) > 1:
                continue

            keys = QKeySequence(*key).toString().split('+')

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

            key_name = "-".join(keys)

            which_key_string[key_name] = s.callback.__name__

        max_width = max(
            self.fontMetrics().horizontalAdvance(f'{key_name} -> {s}')
            for key_name, s in which_key_string.items())

        row_size = self.parentWidget().width() // max_width
        row_num = math.ceil(len(which_key_string) / row_size)

        table = [[] for _ in range(row_num)]
        for i, key_name in enumerate(sorted(which_key_string)):

            shortcut_string = (
                f'<font color=\"darkorchid\"><b>'
                f'{key_name}'
                f'</b></font> &#8594; {which_key_string[key_name]}')

            table[i % row_num].append((max_width, shortcut_string))

        self.setText(html_tabulate(table))
        super().show()

    def cancel(self):
        self.hide()
