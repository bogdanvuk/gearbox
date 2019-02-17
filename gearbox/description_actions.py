import os
from PySide2.QtCore import Qt
from PySide2 import QtGui
from pygears.conf import Inject, reg_inject
from .actions import shortcut


@shortcut('description', Qt.Key_J)
@reg_inject
def line_down(desc=Inject('gearbox/description')):
    desc.moveCursor(QtGui.QTextCursor.Down)


@shortcut('description', Qt.Key_K)
@reg_inject
def line_up(desc=Inject('gearbox/description')):
    desc.moveCursor(QtGui.QTextCursor.Up)


@shortcut('description', Qt.Key_N)
@reg_inject
def trace_next(desc=Inject('gearbox/description')):
    if desc.trace is not None:
        if desc.trace_pos > 0:
            desc.set_trace_pos(desc.trace_pos - 1)


@shortcut('description', Qt.Key_P)
@reg_inject
def trace_prev(desc=Inject('gearbox/description')):
    if desc.trace is not None:
        if desc.trace_pos < len(desc.trace) - 1:
            desc.set_trace_pos(desc.trace_pos + 1)


@shortcut('description', Qt.Key_E)
@reg_inject
def open_external(desc=Inject('gearbox/description')):
    if desc.fn is not None:
        lineno = desc.lineno
        if isinstance(lineno, slice):
            lineno = lineno.start

        os.system(f'emacsclient -n +{lineno} {desc.fn}')
