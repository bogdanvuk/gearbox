from PySide2.QtCore import Qt
from PySide2 import QtWidgets
from pygears.conf import Inject, inject
from .layout import Window, WindowLayout
from .main_window import register_prefix
from .actions import shortcut
from .saver import save

register_prefix(None, (Qt.Key_Space, Qt.Key_W), 'window')


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_D), 'delete')
@inject
def window_delete(layout=Inject('gearbox/layout')):
    if layout.current_layout.win_num > 1:
        window = layout.active_window()
        window.remove()

        next(layout.current_layout.windows()).activate()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_C), 'clear')
@inject
def clear_layout(layout=Inject('gearbox/layout')):
    layout.clear_layout()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_Slash), 'split horizontally')
@inject
def split_horizontally(layout=Inject('gearbox/layout')):
    window = layout.active_window()
    new_window = window.split_horizontally()

    for b in layout.buffers:
        if not b.visible:
            new_window.place_buffer(b)
            return


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_Underscore),
          'split vertically')
@inject
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


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_Plus), 'increase')
@inject
def increase_size(layout=Inject('gearbox/layout')):
    change_perc_size(layout.active_window(), +3)


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_Minus), 'decrease')
@inject
def decrease_size(layout=Inject('gearbox/layout')):
    change_perc_size(layout.active_window(), -3)


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_J), 'down')
@inject
def window_down(layout=Inject('gearbox/layout')):
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

    window = go_down(layout.active_window(), 0)
    if window:
        window.activate()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_K), 'up')
@inject
def window_up(layout=Inject('gearbox/layout')):
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

    window = go_up(layout.active_window(), 0)

    if window:
        window.activate()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_L), 'right')
@inject
def window_right(layout=Inject('gearbox/layout')):
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

    window = go_right(layout.active_window(), 0)
    if window:
        window.activate()


@shortcut(None, (Qt.Key_Space, Qt.Key_W, Qt.Key_H), 'left')
@inject
def window_left(layout=Inject('gearbox/layout')):
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

    window = go_left(layout.active_window(), 0)
    if window:
        window.activate()


register_prefix(None, (Qt.Key_Space, Qt.Key_Q), 'quit')


@shortcut(None, (Qt.Key_Space, Qt.Key_Q, Qt.Key_S), 'save layout')
def save_layout():
    save()
    QtWidgets.QApplication.instance().quit()


@shortcut(None, (Qt.Key_Space, Qt.Key_Q, Qt.Key_Q), 'quit')
def quit():
    QtWidgets.QApplication.instance().quit()


def tab_shortcut_reg(tab_id):
    @shortcut(None, (Qt.ALT + Qt.Key_1 + tab_id), f'tab {tab_id}')
    @inject
    def select_tab(layout=Inject('gearbox/layout')):
        win = layout.current_window
        win.switch_tab(tab_id)


for i in range(10):
    tab_shortcut_reg(i)
