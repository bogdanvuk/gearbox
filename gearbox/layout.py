import os
from .modeline import Modeline
from pygears.conf import Inject, inject, PluginBase, reg, MayInject
from PySide2 import QtCore, QtWidgets, QtGui


@inject
def active_buffer(layout=Inject('gearbox/layout')):
    return layout.current.buff


@inject
def show_buffer(buff, layout=Inject('gearbox/layout')):
    return layout.show_buffer(buff)


class Buffer(QtCore.QObject):
    shown = QtCore.Signal()
    hidden = QtCore.Signal()

    @inject
    def __init__(self,
                 view,
                 name,
                 plugins=None,
                 main=Inject('gearbox/main/inst'),
                 layout=Inject('gearbox/layout')):

        super().__init__()

        view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        menu = main.get_submenu(main.menuBar(), self.domain.title())
        if menu:
            view.customContextMenuRequested.connect(
                lambda pos: menu.popup(view.mapToGlobal(pos)))

        self.view = view
        self.name = name
        layout.add(self)

        if plugins is None:
            try:
                plugins = reg[f'gearbox/plugins/{self.domain}']
            except KeyError:
                plugins = {}

        self.plugins = {}
        for name, cls in plugins.items():
            self.add_plugin(name, cls(self))

    def add_plugin(self, name, plugin):
        self.plugins[name] = plugin

    @property
    @inject
    def window(self, layout=Inject('gearbox/layout')):
        for w in layout.windows:
            if w.buff is self:
                return w
        else:
            return None

    @property
    def active(self):
        return True

    @property
    def visible(self):
        return self.window is not None

    def show(self):
        self.view.show()
        self.shown.emit()

    def hide(self):
        self.view.hide()
        self.hidden.emit()

    def activate(self):
        self.view.setFocus(QtCore.Qt.OtherFocusReason)

    def deactivate(self):
        pass

    @inject
    def delete(self, layout=Inject('gearbox/layout')):
        for name, plugin in self.plugins.items():
            plugin.delete()

        self.plugins.clear()

        if self.window:
            self.window.remove_buffer()

        layout.remove(self)


class Window(QtWidgets.QVBoxLayout):
    buffer_changed = QtCore.Signal()
    activated = QtCore.Signal()
    deactivated = QtCore.Signal()

    @inject
    def __init__(self, parent=None, buff=None,
                 layout=Inject('gearbox/layout')):
        super().__init__()
        self.parent = parent
        self.buff = None

        self.setSpacing(0)
        self.setMargin(0)
        self.setContentsMargins(0, 0, 0, 0)

        self.modeline = Modeline(self)

        local_dir = os.path.abspath(os.path.dirname(__file__))

        pixmap = QtGui.QPixmap(os.path.join(local_dir, 'logo.png'))

        self.tab_change_lock = False
        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.addTab('**')
        self.tab_bar.currentChanged.connect(self.switch_tab)
        for b in layout.buffers:
            self.new_buffer(b)

        layout.new_buffer.connect(self.new_buffer)
        layout.buffer_removed.connect(self.buffer_removed)

        self.placeholder = QtWidgets.QLabel()
        self.placeholder.setPixmap(pixmap)
        self.placeholder.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        self.placeholder.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                       QtWidgets.QSizePolicy.Ignored)
        # self.placeholder.setStyleSheet(themify(STYLE_MINIBUFFER))
        self.placeholder.setAlignment(QtCore.Qt.AlignHCenter
                                      | QtCore.Qt.AlignVCenter)

        self.buf_layout_pos = 1
        self.layout_full_size = 4
        self.addWidget(self.tab_bar)
        self.addWidget(self.placeholder, 1)
        self.addWidget(self.modeline)

        if not reg['gearbox/main/tabbar']:
            self.tab_bar.hide()

        if buff is not None:
            self.placeholder.hide()
            self.insertWidget(self.buf_layout_pos, buff.view, stretch=1)
            self.buff = buff
            self.buff.show()

    def tab_index_by_name(self, name):
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabText(i) == name:
                return i

        return None

    def new_buffer(self, buff):
        self.tab_bar.addTab(buff.name)

    def buffer_removed(self, buff):
        i = self.tab_index_by_name(buff.name)
        self.tab_bar.removeTab(i)

    @inject
    def switch_tab(self, index, layout=Inject('gearbox/layout')):
        if self.tab_change_lock:
            return

        name = self.tab_bar.tabText(index)
        if name == '**':
            self.remove_buffer()
        else:
            for buff in layout.buffers:
                if buff.name == name:
                    self.place_buffer(buff)
                    return

    def _switch_tab(self, index):
        # if index == self.tab_bar.currentIndex():
        #     print("Skip moving")
        #     return

        self.tab_change_lock = True
        # self.tab_bar.moveTab(index, 0)
        # self.tab_bar.setCurrentIndex(0)
        self.tab_bar.setCurrentIndex(index)
        self.tab_change_lock = False

    def split_horizontally(self):
        return self.parent.split_horizontally(self)

    def split_vertically(self):
        return self.parent.split_vertically(self)

    def get_window(self, position):
        return self

    def deactivate(self):
        if self.buff:
            self.buff.deactivate()

        self.deactivated.emit()

    def remove(self):
        self.remove_buffer()
        self.parent.remove_child(self)
        for _ in range(self.layout_full_size-1):
            self.removeItem(self.itemAt(0))

        self.placeholder.setParent(None)
        self.placeholder.deleteLater()
        self.tab_bar.setParent(None)
        self.tab_bar.deleteLater()
        self.modeline.remove()
        self.setParent(None)
        self.deleteLater()

    @inject
    def activate(self, layout=Inject('gearbox/layout')):
        layout.window_activated(self)

        if self.buff:
            self.buff.activate()

        self.activated.emit()

    @inject
    def remove_buffer(self, switch=True, main=Inject('gearbox/main/inst')):
        if self.buff:
            # print(f'Removing buffer {self.buff} from window: {self.position}')
            if switch:
                self._switch_tab(0)

            # If widget has not been automatically removed by some other action
            if self.count() == self.layout_full_size:
                self.removeItem(self.itemAt(self.buf_layout_pos))
                self.buff.view.setParent(main)

            self.modeline.reset()
            self.placeholder.show()
            self.buff.hide()
            self.buff = None
            self.buffer_changed.emit()

    def place_buffer(self, buff, position=None):
        # print(f'Placing buffer {buff} to window: {self.position}. Prev buffer {self.buff}')
        self.remove_buffer(switch=False)

        self.placeholder.hide()

        if buff.window:
            buff.window.remove_buffer()

        i = self.tab_index_by_name(buff.name)
        self._switch_tab(i)

        self.insertWidget(self.buf_layout_pos, buff.view, stretch=1)
        self.buff = buff
        self.buff.show()
        self.activate()
        self.buffer_changed.emit()
        # print("Buffer placed!")

    @property
    @inject
    def active(self, layout=Inject('gearbox/layout')):
        return layout.current_window is self

    @property
    def win_num(self):
        return 1

    @property
    def win_id(self):
        return self.parent.child_win_id(self)

    @property
    def position(self):
        return self.parent.child_position(self)

    @property
    def current(self):
        if self.buff is None:
            return None
        elif self.buff.view.hasFocus():
            return self
        else:
            return None


def child_iter(layout):
    for i in range(layout.count()):
        yield layout.child(i)


class WindowLayout(QtWidgets.QBoxLayout):
    def __init__(self, parent, size, direction=None):
        if direction is None:
            direction = QtWidgets.QBoxLayout.LeftToRight

        super().__init__(direction)

        self.parent = parent
        self.setSpacing(0)
        self.setMargin(0)
        self.setContentsMargins(0, 0, 0, 0)

        if size:
            for i in range(size):
                self.addLayout(Window())

            self.equalize_stretch()

    @property
    def current(self):
        for i in range(self.count()):
            ret = self.itemAt(i).layout().current
            if ret:
                return ret

    def __iter__(self):
        return child_iter(self)

    @property
    def position(self):
        return self.parent.child_position(self)

    def child_win_id(self, child):
        win_id = self.parent.child_win_id(self)

        if self.child_index(child) is None:
            import pdb
            pdb.set_trace()

        for i in range(self.child_index(child)):
            win_id += self.child(i).win_num

        return win_id

    def windows(self):
        for child in self:
            if isinstance(child, Window):
                yield child
            else:
                yield from child.windows()

    @property
    def win_num(self):
        win_cnt = 0
        for i in range(self.count()):
            win_cnt += self.child(i).win_num
        return win_cnt

    def child_position(self, child):
        return self.position + (self.child_index(child), )

    def child(self, index):
        if index == -1:
            index = self.count() - 1

        return self.itemAt(index).layout()

    def child_index(self, child):
        for i in range(self.count()):
            if self.itemAt(i).layout() is child:
                return i

    def addLayout(self, layout):
        super().addLayout(layout)
        layout.parent = self
        self.equalize_stretch()
        if isinstance(layout, Window):
            layout.modeline.update()

    def equalize_stretch(self):
        for i in range(self.count()):
            self.setStretch(i, round(100 / self.count()))

    def insert_child(self, pos):
        child = Window(self)
        self.insertLayout(pos, child)
        self.equalize_stretch()
        child.modeline.update()
        return child

    @inject
    def remove_child(self, child, layout=Inject('gearbox/layout')):
        pos = self.child_index(child)
        self.removeItem(self.itemAt(pos))
        layout.current_window = None

    def split_horizontally(self, child):
        if (self.direction() !=
                QtWidgets.QBoxLayout.LeftToRight) and (self.count() == 1):
            self.setDirection(QtWidgets.QBoxLayout.LeftToRight)

        if (self.direction() == QtWidgets.QBoxLayout.LeftToRight):
            pos = self.child_index(child)
            return self.insert_child(pos + 1)
        else:
            stretches = [self.stretch(i) for i in range(self.count())]
            pos = self.child_index(child)
            child_layout = WindowLayout(
                self, size=0, direction=QtWidgets.QBoxLayout.LeftToRight)
            self.insertLayout(pos, child_layout)
            self.removeItem(child)
            child_layout.addLayout(child)
            child_layout.insert_child(0)

            for i, s in enumerate(stretches):
                self.setStretch(i, s)

            return child_layout.child(0)

    def split_vertically(self, child):
        if (self.direction() !=
                QtWidgets.QBoxLayout.TopToBottom) and (self.count() == 1):
            self.setDirection(QtWidgets.QBoxLayout.TopToBottom)

        if (self.direction() == QtWidgets.QBoxLayout.TopToBottom):
            pos = self.child_index(child)
            return self.insert_child(pos + 1)
        else:
            stretches = [self.stretch(i) for i in range(self.count())]
            pos = self.child_index(child)
            child_layout = WindowLayout(
                self, size=0, direction=QtWidgets.QBoxLayout.TopToBottom)
            self.insertLayout(pos, child_layout)
            self.removeItem(child)
            child_layout.addLayout(child)
            child_layout.insert_child(0)

            for i, s in enumerate(stretches):
                self.setStretch(i, s)

            return child_layout.child(0)

    def get_window(self, position):
        return self.child(position[0]).get_window(position[1:])

    def place_buffer(self, buff, position):
        self.get_window(position).place_buffer(buff, [])


class BufferStack(QtWidgets.QStackedLayout):
    new_buffer = QtCore.Signal(object)
    buffer_removed = QtCore.Signal(object)

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.current_window = None
        self.current_layout = None
        self.current_layout_widget = None

        QtWidgets.QApplication.instance().focusChanged.connect(self.focus_changed)

        self.main = main
        self.setMargin(0)
        self.setContentsMargins(0, 0, 0, 0)
        self.buffers = []

        reg['gearbox/layout'] = self

        self.clear_layout()

        # self.currentChanged.connect(self.current_changed)

    def clear(self):
        self.clear_layout()
        self.clear_buffers()

    def clear_buffers(self):
        for b in self.buffers.copy():
            b.delete()

    def clear_layout(self):
        if self.current_layout:
            for w in self.windows:
                w.remove_buffer()

        self.current_layout = WindowLayout(self, 1)
        if self.current_layout_widget:
            self.removeWidget(self.current_layout_widget)
            self.current_layout_widget.deleteLater()

        self.current_layout_widget = QtWidgets.QWidget()
        self.current_layout_widget.setLayout(self.current_layout)
        self.addWidget(self.current_layout_widget)

        self.current_window = None
        self.activate_window([0])

        # for b in self.buffers:
        #     b.hide()

    def child_win_id(self, child):
        return 1

    def child_position(self, child):
        return tuple()

    def place_buffer(self, buf, position):
        self.current_layout.place_buffer(buf, position)
        self.activate_window(position)

    def get_window(self, position):
        return self.current_layout.get_window(position)

    @property
    def windows(self):
        return list(self.current_layout.windows())

    def active_window(self):
        return self.current_window

    def window_activated(self, win):
        last_window = self.current_window
        self.current_window = win

        if last_window:
            last_window.deactivate()

        if win.buff:
            self.main.change_domain(win.buff.domain)

    def activate_window(self, position):
        self.get_window(position).activate()

    def get_buffer_by_name(self, name):
        for b in self.buffers:
            if b.name == name:
                return b
        else:
            return None

    def remove(self, buf):
        # print(f"Removing {buf} from layout")
        self.buffers.remove(buf)
        self.buffer_removed.emit(buf)

    def show_buffer(self, buf):
        if buf.visible:
            return

        def find_empty_position(layout):
            if isinstance(layout, Window):
                if layout.buff is None:
                    return layout
            else:
                for i in range(layout.count()):
                    buff = find_empty_position(layout.child(i))
                    if buff is not None:
                        return buff

        empty_pos = find_empty_position(self.current_layout)

        if empty_pos:
            win = empty_pos
        elif len(self.windows) == 1:
            win = self.windows[0]
        else:
            for w in self.windows:
                if w is not self.current:
                    win = w
                    break

        win.place_buffer(buf)
        win.activate()

    def add(self, buf):
        # print(f"Adding {buf.name} to layout")
        self.buffers.append(buf)
        self.new_buffer.emit(buf)

    @property
    def current(self):
        return self.current_window
        # return self.current_layout.current
        # try:
        #     # return list(self._buffers.values())[self.currentIndex()]
        #     return list(self._buffers.values())[0]
        # except KeyError:
        #     return None

    @property
    def current_name(self):
        if self.current.buff:
            return self.current.buff.name
        else:
            return None

    def focus_changed(self, old, now):
        def get_widget_window(w):
            for win in self.windows:
                if win.indexOf(w) >= 0:
                    return win
            else:
                return None

        old_focus_win = get_widget_window(old)
        if not old_focus_win:
            return

        new_focus_win = get_widget_window(now)
        if new_focus_win and not new_focus_win.active:
            print(f'Focus changed: {old_focus_win.position} -> {new_focus_win.position}')
            new_focus_win.activate()


class LayoutPlugin(PluginBase):
    @classmethod
    def bind(cls):
        reg['gearbox/plugins'] = {}

        @inject
        def tab_bar_visibility(var,
                               visible,
                               layout=MayInject('gearbox/layout')):
            if layout:
                for w in layout.windows:
                    w.tab_bar.setVisible(visible)

        reg.confdef(
            'gearbox/main/tabbar', default=True, setter=tab_bar_visibility)
