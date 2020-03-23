import math
from . import html_utils

from PySide2.QtWidgets import QLabel
from pygears.conf import Inject, reg, inject
from PySide2.QtGui import QKeySequence
from PySide2 import QtCore


@inject
def which_key(main=Inject('gearbox/main/inst')):
    w = WhichKey(main)
    main.vbox.insertWidget(main.vbox.count() - 1, w)
    reg['gearbox/which_key'] = w


class WhichKey(QLabel):
    @inject
    def __init__(self, parent=None, main=Inject('gearbox/main/inst')):
        super().__init__(parent)
        self.setMargin(2)
        self.hide()
        # parent.installEventFilter(self)
        main.installEventFilter(self)
        main.minibuffer.start.connect(self.cancel)
        main.key_cancel.connect(self.cancel)
        # main.domain_changed.connect(self.domain_changed)
        self.prefixes = []
        self.current_prefix = []
        self.prefix_detected = False
        self.timer = QtCore.QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.show)
        self.timer.setSingleShot(True)

    @inject
    def is_prefix(self, key, main=Inject('gearbox/main/inst')):
        prefix = self.current_prefix + [key]
        for s in main.shortcuts:
            if not s.enabled:
                continue

            if len(prefix) >= len(s.key):
                continue

            if all(k1 == k2 for k1, k2 in zip(prefix, s.key)):
                return True

    def eventFilter(self, obj, event):
        # if event.type() == QtCore.QEvent.ShortcutOverride:
        if event.type() == QtCore.QEvent.KeyRelease:
            if self.is_prefix(event.key()):
                self.current_prefix.append(event.key())
                # print(f"Prefix extended: {self.current_prefix}")
                if self.isVisible():
                    self.show()
                else:
                    self.timer.start()

                self.prefix_detected = True

            if self.current_prefix and (not self.prefix_detected):
                self.cancel()

            self.prefix_detected = False

        return super().eventFilter(obj, event)

    # @inject
    # def domain_changed(self, domain, main=Inject('gearbox/main/inst')):
    #     self.prefixes.clear()
    #     for s in main.shortcuts:
    #         if (s.domain is None and domain[0] != '_') or (s.domain == domain):
    #             if len(s.key) > 1:
    #                 self.prefixes[s.key[0]] = s

    @inject
    def show(self,
             main=Inject('gearbox/main/inst'),
             domain=Inject('gearbox/domain'),
             prefixes=Inject('gearbox/prefixes')):

        which_key_string = {}
        for s in main.shortcuts:
            if not s.enabled:
                continue

            key = s.key

            if self.current_prefix:
                if any(k != p for k, p in zip(s.key, self.current_prefix)):
                    continue
                else:
                    key = key[len(self.current_prefix):]

            key_group = False
            if len(key) > 1:
                key_group = True
                key = key[0:1]
                # continue

            if key[0] == QtCore.Qt.Key_Plus:
                keys = ['+']
            else:
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

            if shift_id is None and keys[0].isalpha():
                keys[0] = keys[0].lower()

            if ctrl_id is not None:
                keys.insert(0, 'C')

            key_name = "-".join(keys)

            if not key_group:
                which_key_string[key_name] = (s.name, s.name)
            else:
                group_name = prefixes.get((domain,
                                           tuple(self.current_prefix) + key))
                if not group_name:
                    group_name = prefixes.get(
                        (None, tuple(self.current_prefix) + key))

                if not group_name:
                    group_name = 'group'

                which_key_string[key_name] = (group_name,
                                              html_utils.fontify(
                                                  group_name,
                                                  color='#749dff'))

        max_width = max(
            self.fontMetrics().horizontalAdvance(f'{key_name} -> {s}')
            for key_name, (s, _) in which_key_string.items())

        row_size = self.parentWidget().width() // max_width
        row_num = math.ceil(len(which_key_string) / row_size)

        table = [[] for _ in range(row_num)]
        for i, key_name in enumerate(sorted(which_key_string)):

            shortcut_string = (
                html_utils.fontify(key_name, color='darkorchid') +
                f' &#8594; {which_key_string[key_name][1]}')

            table[i % row_num].append((f'width={max_width}', shortcut_string))

        self.setText(html_utils.tabulate(table))
        super().show()

    def cancel(self):
        self.timer.stop()
        self.current_prefix.clear()
        self.hide()
        self.prefix_detected = False
