from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, inject
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
        f.setPointSize(12)
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
    @inject
    def __init__(self,
                 main=Inject('gearbox/main/inst')):

        Shortcut('graph', QtCore.Qt.Key_F, self.snipe_select)
        Shortcut('graph', QtCore.Qt.CTRL + QtCore.Qt.Key_F,
                 self.snipe_select_nodes)
        Shortcut('graph', QtCore.Qt.SHIFT + QtCore.Qt.Key_F,
                 self.snipe_select_pipes)

        self.main = main

    @inject
    def snipe_cancel(self, graph=Inject('gearbox/graph')):
        self.main.key_cancel.disconnect(self.snipe_cancel)
        for text, s in snipe_shortcuts:
            s.setParent(None)
            graph.scene().removeItem(text)

        self.main.change_domain('graph')
        snipe_shortcuts.clear()

    @inject
    def snipe_shot(self, pipe, graph=Inject('gearbox/graph')):
        graph.select(pipe)
        self.snipe_cancel()

    @inject
    def snipe_shot_prefix(self, prefix, graph=Inject('gearbox/graph')):
        import pdb
        pdb.set_trace()
        for text, s in snipe_shortcuts:
            if text.toPlainText().startswith(prefix):
                continue

            s.setParent(None)
            graph.scene().removeItem(text)

    def snipe_shot_prefix_test(self):
        print("Ambiguous")

    def get_visible_objs(self, node, objtype):
        if (objtype is None) or (objtype is NodeItem):
            for n in node._nodes:
                yield n
                if not n.collapsed:
                    yield from self.get_visible_objs(n, objtype)

        if (objtype is None) or (objtype is Pipe):
            for p in node.pipes:
                yield p

    def snipe_select_nodes(self):
        self.snipe_select(objtype=NodeItem)

    def snipe_select_pipes(self):
        self.snipe_select(objtype=Pipe)

    @inject
    def snipe_select(self, objtype=None, graph=Inject('gearbox/graph')):
        self.main.key_cancel.connect(self.snipe_cancel)

        nodes = graph.selected_nodes()

        nodes = [
            node.parent if node.collapsed else node for node in nodes
        ]

        if not nodes:
            pipes = graph.selected_pipes()
            if not pipes:
                nodes = [graph.top]
            else:
                nodes = [pipe.parent for pipe in pipes]

        keys = [2]

        for n in nodes:
            if n.collapsed:
                continue

            for i, obj in enumerate(self.get_visible_objs(n, objtype=objtype)):
                key_codes = [key + ord('A') for key in reversed(keys)]
                snipe_text = ''.join([chr(key).upper() for key in key_codes])
                text = SnipeCodeItem(snipe_text)

                text.setZValue(100)
                graph.scene().addItem(text)

                if isinstance(obj, NodeItem):
                    text.setPos(
                        obj.mapToScene((obj.boundingRect().bottomLeft() + obj.
                                        boundingRect().bottomRight()) / 2) -
                        QtCore.QPointF(text.boundingRect().width() / 2,
                                       text.boundingRect().height()))
                else:
                    text.setPos(
                        obj.mapToScene(obj.path().pointAtPercent(0.5)) -
                        QtCore.QPointF(text.boundingRect().width(),
                                       text.boundingRect().height()) / 2)

                self.main.change_domain('_snipe')
                shortcut = QtWidgets.QShortcut(
                    QtGui.QKeySequence(*key_codes), self.main)

                shortcut.activated.connect(partial(self.snipe_shot, obj))

                # if len(keys) > 0:
                #     shortcut.activatedAmbiguously.connect(
                #         self.snipe_shot_prefix_test)
                # shortcut.activatedAmbiguously.connect(
                #     partial(
                #         self.snipe_shot_prefix, prefix=snipe_text[:-1]))

                snipe_shortcuts.append((text, shortcut))

                for pos in range(len(keys) + 1):
                    if pos == len(keys):
                        keys.insert(0, 0)
                        break

                    keys[pos] += 1

                    if keys[pos] < 25:
                        break
                    else:
                        keys[pos] = 0
