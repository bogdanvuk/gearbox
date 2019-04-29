import os
from PySide2.QtCore import Qt
from PySide2 import QtGui
from pygears.conf import Inject, inject
from .actions import shortcut
from .layout import active_buffer


@shortcut('description', Qt.Key_J)
def line_down():
    active_buffer().view.moveCursor(QtGui.QTextCursor.Down)


@shortcut('description', Qt.Key_K)
def line_up():
    active_buffer().view.moveCursor(QtGui.QTextCursor.Up)


@shortcut('description', Qt.Key_N)
def trace_next():
    desc = active_buffer().view
    if desc.trace is not None:
        if desc.trace_pos > 0:
            desc.set_trace_pos(desc.trace_pos - 1)


@shortcut('description', Qt.Key_P)
def trace_prev():
    desc = active_buffer().view
    if desc.trace is not None:
        if desc.trace_pos < len(desc.trace) - 1:
            desc.set_trace_pos(desc.trace_pos + 1)


@shortcut('description', Qt.Key_E)
def open_external():
    desc = active_buffer().view
    if desc.fn is not None:
        lineno = desc.lineno
        if isinstance(lineno, slice):
            lineno = lineno.start

        os.system(f'emacsclient -n +{lineno} {desc.fn}')
