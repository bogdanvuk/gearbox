#!/usr/bin/python
import sys

from PySide2 import QtWidgets, QtCore, QtGui

from pygears_view.graph import NodeGraph
from pygears import bind
from pygears.conf.log import INFO
from pygears.common import add, shred
from pygears.util.print_hier import print_hier
from pygears.conf import Inject, reg_inject
from pygears_view.node import NodeItem

# class App(QtWidgets.QApplication):
#     @reg_inject
#     def eventFilter(self, obj, event, shortcuts=Inject('graph/shortcuts')):
#         print(f"{event.type()}: {obj}")
#         if event.type() == QtCore.QEvent.Type.MetaCall:
#             if hasattr(self, 'prebac'):
#                 print(f"    {dir(event)}")

#         if type(obj) == QtGui.QWindow:
#             if event.type() == QtCore.QEvent.KeyPress:
#                 print(f"{event.key()}: {obj}")
#                 for shortcut, callback in shortcuts:
#                     if shortcut == event.key():
#                         self.prebac = True
#                         # if event.matches(shortcut):
#                         callback()
#                         # return True

#                 # print("Ate key press", event.key())
#                 # return True
#             # else:
#             # standard event processing
#             return super().eventFilter(obj, event)


@reg_inject
def main(root=Inject('gear/hier_root')):
    # app = App(sys.argv)
    # app.installEventFilter(app)
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Source Code Pro", 13))

    # create node graph.
    graph = NodeGraph()

    viewer = graph.viewer()
    viewer.setWindowTitle('My Node Graph')
    viewer.resize(800, 500)
    viewer.setGeometry(500, viewer.y(), 800, 500)

    bind('logger/util/level', INFO)
    print_hier()

    top = NodeItem(root, graph)
    graph.top = top
    top.layout()
    top.graph.fit_all()

    graph.show()
    app.exec_()
