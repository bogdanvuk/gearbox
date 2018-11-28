from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, reg_inject
from .node import NodeItem
from .pipe import Pipe
from .main_window import Shortcut
from functools import partial

snipe_shortcuts = []


def sniper():
    Sniper()


class SnipeCodeItem(QtWidgets.QGraphicsTextItem):
    def __init__(self, text, parent=None):
        super().__init__(text, parent=parent)
        f = self.font()
        f.setPointSize(14)
        f.setBold(True)
        self.setFont(f)

        # self.font().setPointSize(16)
        # self.font().setBold(True)
        # # self.setFont(self.font())
        # self.setFont(QtGui.QFont("Source Code Pro", 16))

    def paint(self, painter, option, widget):
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(self.boundingRect())
        super().paint(painter, option, widget)


class Sniper:
    @reg_inject
    def __init__(self,
                 main=Inject('viewer/main'),
                 graph=Inject('viewer/graph')):

        Shortcut('graph', QtCore.Qt.Key_F, self.snipe_select)
        Shortcut('graph', QtCore.Qt.CTRL + QtCore.Qt.Key_F,
                 self.snipe_select_nodes)
        Shortcut('graph', QtCore.Qt.SHIFT + QtCore.Qt.Key_F,
                 self.snipe_select_pipes)

        self.main = main
        self.graph = graph
        self.main.key_cancel.connect(self.snipe_cancel)

    def snipe_cancel(self):
        for text, s in snipe_shortcuts:
            s.setParent(None)
            # s.deleteLater()
            self.graph.scene().removeItem(text)

        self.main.change_domain('graph')
        snipe_shortcuts.clear()

    def snipe_shot(self, pipe):
        self.graph.select(pipe)
        self.snipe_cancel()

    def get_visible_objs(self, node, objtype):
        if (objtype is None) or (objtype is NodeItem):
            for n in node._nodes:
                yield n
                if not n.collapsed:
                    yield from self.get_visible_objs(n)

        if (objtype is None) or (objtype is Pipe):
            for p in node.pipes:
                yield p

    def snipe_select_nodes(self):
        self.snipe_select(objtype=NodeItem)

    def snipe_select_pipes(self):
        self.snipe_select(objtype=Pipe)

    def snipe_select(self, objtype=None):
        nodes = self.graph.selected_nodes()
        if not nodes:
            nodes = [self.graph.top]

        for n in nodes:
            for i, obj in enumerate(self.get_visible_objs(n, objtype=objtype)):
                key = ord('A') + i
                text = SnipeCodeItem(chr(key).upper())
                text.setZValue(100)
                self.graph.scene().addItem(text)

                if isinstance(obj, NodeItem):
                    text.setPos(
                        obj.mapToScene((obj.boundingRect().bottomLeft() +
                                        obj.boundingRect().bottomRight()) / 2)
                        - QtCore.QPointF(text.boundingRect().width() / 2,
                                         text.boundingRect().height()))
                else:
                    text.setPos(
                        obj.mapToScene(obj.path().pointAtPercent(0.5)) -
                        QtCore.QPointF(text.boundingRect().width(),
                                       text.boundingRect().height()) / 2)

                self.main.change_domain('_snipe')
                shortcut = QtWidgets.QShortcut(
                    QtGui.QKeySequence(key), self.main)
                shortcut.activated.connect(partial(self.snipe_shot, obj))
                snipe_shortcuts.append((text, shortcut))
