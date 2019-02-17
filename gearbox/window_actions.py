import os
from PySide2.QtCore import Qt
from PySide2 import QtWidgets
from pygears.conf import Inject, reg_inject, registry
from .layout import Window, WindowLayout
from .main_window import register_prefix
from .actions import shortcut
from .saver import save

register_prefix(None, (Qt.Key_Space, Qt.Key_F), 'file')


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.Key_F))
@reg_inject
def open_file(sim_bridge=Inject('gearbox/sim_bridge')):
    ret = QtWidgets.QFileDialog.getOpenFileName(
        caption='Open file',
        dir=os.getcwd(),
        filter="PyGears script (*.py);;All files (*)")

    script_fn = ret[0]

    if script_fn:
        registry('gearbox/sim_bridge').invoke_method(
            'run_model', script_fn=script_fn)

        registry('gearbox/sim_bridge').invoke_method('run_sim')


register_prefix(None, (Qt.Key_Space, Qt.Key_W), 'window')


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_D))
@reg_inject
def window_delete(layout=Inject('gearbox/layout')):
    if layout.current_layout.win_num > 1:
        window = layout.active_window()
        window.remove()

        next(layout.current_layout.windows()).activate()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_Slash))
@reg_inject
def split_horizontally(layout=Inject('gearbox/layout')):
    window = layout.active_window()
    new_window = window.split_horizontally()

    for b in layout.buffers:
        if not b.visible:
            new_window.place_buffer(b)
            return


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_Underscore))
@reg_inject
def split_vertically(layout=Inject('gearbox/layout')):
    window = layout.active_window()
    new_window = window.split_vertically()
    for b in layout.buffers:
        if not b.visible:
            new_window.place_buffer(b)
            return


def change_perc_size(window, diff):
    parent = window.parent
    index = parent.child_index(window)

    prev_stretch = parent.stretch(index)
    cur_stretch = prev_stretch + diff
    prev_remain_stretch = 100 - prev_stretch
    remain_stretch = 100 - cur_stretch

    parent.setStretch(index, cur_stretch)

    for i in range(parent.count()):
        if i != index:
            prev_stretch = parent.stretch(i)
            parent.setStretch(
                i, round(prev_remain_stretch / prev_stretch * remain_stretch))


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_Plus))
@reg_inject
def increase_height(layout=Inject('gearbox/layout')):
    change_perc_size(layout.active_window(), +3)


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_Minus))
@reg_inject
def decrease_height(layout=Inject('gearbox/layout')):
    change_perc_size(layout.active_window(), -3)


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_J))
@reg_inject
def window_down(main=Inject('gearbox/main')):
    def go_topmost_down(window):
        if isinstance(window, Window):
            return window
        else:
            return go_topmost_down(window.child(0))

    def go_down(window, pos):
        if (isinstance(window, WindowLayout) and (window.count() > 1)
                and (window.direction() == QtWidgets.QBoxLayout.TopToBottom)):
            if pos < window.count() - 1:
                return go_topmost_down(window.child(pos + 1))

        else:
            parent = window.parent
            return go_down(parent, parent.child_index(window))

    window = go_down(main.buffers.active_window(), 0)
    if window:
        window.activate()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_K))
@reg_inject
def window_up(main=Inject('gearbox/main')):
    def go_bottommost_down(window):
        if isinstance(window, Window):
            return window
        else:
            return go_bottommost_down(window.child(-1))

    def go_up(window, pos):
        if (isinstance(window, WindowLayout) and (window.count() > 1)
                and (window.direction() == QtWidgets.QBoxLayout.TopToBottom)):
            if pos > 0:
                return go_bottommost_down(window.child(pos - 1))

        else:
            parent = window.parent
            return go_up(parent, parent.child_index(window))

    window = go_up(main.buffers.active_window(), 0)

    if window:
        window.activate()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_L))
@reg_inject
def window_right(main=Inject('gearbox/main')):
    def go_leftmost_down(window):
        if isinstance(window, Window):
            return window
        else:
            return go_leftmost_down(window.child(0))

    def go_right(window, pos):
        if (isinstance(window, WindowLayout) and (window.count() > 1)
                and (window.direction() == QtWidgets.QBoxLayout.LeftToRight)):
            if pos < window.count() - 1:
                return go_leftmost_down(window.child(pos + 1))

        else:
            parent = window.parent
            return go_right(parent, parent.child_index(window))

    window = go_right(main.buffers.active_window(), 0)
    if window:
        window.activate()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_H))
@reg_inject
def window_left(main=Inject('gearbox/main')):
    def go_rightmost_down(window):
        if isinstance(window, Window):
            return window
        else:
            return go_rightmost_down(window.child(-1))

    def go_left(window, pos):
        if (isinstance(window, WindowLayout) and (window.count() > 1)
                and (window.direction() == QtWidgets.QBoxLayout.LeftToRight)):
            if pos > 0:
                return go_rightmost_down(window.child(pos - 1))

        else:
            parent = window.parent
            return go_left(parent, parent.child_index(window))

    window = go_left(main.buffers.active_window(), 0)
    if window:
        window.activate()


register_prefix(None, (Qt.Key_Space, Qt.Key_Q), 'quit')


@shortcut(None, (Qt.Key_Space, Qt.Key_Q, Qt.Key_S))
def save_layout():
    save()
    QtWidgets.QApplication.instance().quit()


@shortcut(None, (Qt.Key_Space, Qt.Key_Q, Qt.Key_Q))
def quit():
    QtWidgets.QApplication.instance().quit()
