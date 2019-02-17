import os
from .modeline import Modeline
from pygears.conf import Inject, reg_inject, safe_bind
from PySide2 import QtCore, QtWidgets, QtGui
from .stylesheet import STYLE_MINIBUFFER


@reg_inject
def active_buffer(layout=Inject('gearbox/layout')):
    return layout.current.buff


class Buffer:
    def __init__(self, view, name):
        self.view = view
        self.name = name
        self.window = None

    @property
    def active(self):
        return True

    @property
    def visible(self):
        return self.window is not None

    def show(self, window):
        if self.window:
            self.window.remove_buffer()

        self.window = window
        self.view.show()

    def hide(self):
        self.window = None
        self.view.hide()

    def activate(self):
        self.view.setFocus(QtCore.Qt.OtherFocusReason)

    def deactivate(self):
        pass


class Window(QtWidgets.QVBoxLayout):
    @reg_inject
    def __init__(self, parent=None, buff=None):
        super().__init__()
        self.parent = parent
        self.buff = None

        self.setSpacing(0)
        self.setMargin(0)
        self.setContentsMargins(0, 0, 0, 0)

        self.modeline = Modeline(self)

        local_dir = os.path.abspath(os.path.dirname(__file__))

        pixmap = QtGui.QPixmap(os.path.join(local_dir, 'logo.png'))
        self.placeholder = QtWidgets.QLabel()
        self.placeholder.setPixmap(pixmap)
        self.placeholder.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        self.placeholder.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                       QtWidgets.QSizePolicy.Ignored)
        self.placeholder.setStyleSheet(STYLE_MINIBUFFER)
        self.placeholder.setAlignment(QtCore.Qt.AlignHCenter
                                      | QtCore.Qt.AlignVCenter)

        self.addWidget(self.placeholder, 1)
        self.addWidget(self.modeline)

        if buff is not None:
            # self.place_buffer(buff)
            self.placeholder.hide()
            view = buff.view

            self.insertWidget(0, view, stretch=1)
            view.show()

            self.buff = buff
            self.buff.show(self)

    def split_horizontally(self):
        return self.parent.split_horizontally(self)

    def split_vertically(self):
        return self.parent.split_vertically(self)

    def get_window(self, position):
        return self

    def deactivate(self):
        if self.buff:
            self.buff.deactivate()

        self.modeline.update()

    def remove(self):
        self.remove_buffer()
        self.parent.remove_child(self)
        self.removeItem(self.itemAt(0))
        self.removeItem(self.itemAt(0))
        self.placeholder.setParent(None)
        self.placeholder.deleteLater()
        self.modeline.remove()
        self.setParent(None)
        self.deleteLater()

    @reg_inject
    def activate(self, layout=Inject('gearbox/layout')):
        if self.buff:
            self.buff.activate()

        layout.window_activated(self)
        self.modeline.update()

    def remove_buffer(self):
        if self.buff:
            print(f'Removing buffer {self.buff} from window: {self.position}')
            # If widget has not been automatically removed by some other action
            if self.count() == 3:
                self.removeItem(self.itemAt(0))

            self.placeholder.show()
            self.buff.hide()
            self.buff = None

    def place_buffer(self, buff, position=None):
        self.remove_buffer()
        self.placeholder.hide()

        view = buff.view

        self.insertWidget(0, view, stretch=1)
        view.show()

        self.buff = buff
        self.buff.show(self)
        self.activate()

    @property
    @reg_inject
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
        if self.buff.view.hasFocus():
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

    @reg_inject
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
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.current_layout_widget = QtWidgets.QWidget()
        self.current_window = None

        safe_bind('gearbox/layout', self)

        # layout = WindowLayout(size=1)
        self.current_layout = WindowLayout(self, 1)
        self.current_layout_widget.setLayout(self.current_layout)
        self.addWidget(self.current_layout_widget)

        self.main = main
        self.setMargin(0)
        self.setContentsMargins(0, 0, 0, 0)
        self.buffers = []
        self.currentChanged.connect(self.current_changed)

    def child_win_id(self, child):
        return 1

    def child_position(self, child):
        return tuple()

    def place_buffer(self, buf, position):
        self.current_layout.place_buffer(buf, position)
        self.activate_window(position)

    def get_window(self, position):
        return self.current_layout.get_window(position)

    def windows(self):
        yield from self.current_layout.windows()

    def active_window(self):
        return self.current_layout.current

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

    def add(self, buf):
        self.buffers.append(buf)

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
            empty_pos.place_buffer(buf)
            empty_pos.activate()

    def current_changed(self):
        self.main.modeline.setText(self.current.name)
        if hasattr(self.current, 'activate'):
            self.current.activate()

        self.main.change_domain(self.current.domain)

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
