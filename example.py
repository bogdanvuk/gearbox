#!/usr/bin/python
import sys

from PySide2 import QtWidgets

from pygears_view.graph import NodeGraph, find_node_by_path
from pygears import bind
from pygears.conf.log import INFO
from pygears.common import add, shred
from pygears.util.print_hier import print_hier
from pygears.conf import Inject, reg_inject
from pygears_view.node import NodeItem

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    # create node graph.
    graph = NodeGraph()

    viewer = graph.viewer()
    viewer.setWindowTitle('My Node Graph')
    viewer.resize(800, 500)
    viewer.setGeometry(500, viewer.y(), 800, 500)

    add(2, 4) | shred
    # const(val=2) | shred

    bind('logger/util/level', INFO)
    print_hier()

    @reg_inject
    def make_graph(
            root=Inject('gear/hier_root'), params=False, fullname=False):

        top = NodeItem(root, graph)
        top.layout()
        top.graph.center_selection()
        return top

    top = make_graph()
    graph.top = top

    # node = find_node_by_path(graph.top, 'shred')
    # print(node)

    graph.show()
    app.exec_()

# import sys

# from PySide2 import QtGui

# class SomeScene(QtWidgets.QGraphicsScene):
#     def __init__(self, parent = None):
#         QtWidgets.QGraphicsScene.__init__(self, parent)

#         pixmap = QtGui.QPixmap('someImage')
#         item = QtWidgets.QGraphicsPixmapItem(pixmap)
#         self.addItem(item)


# class MainWindow(QtWidgets.QMainWindow):
#     def __init__(self, parent = None):
#         QtWidgets.QMainWindow.__init__(self, parent)

#         # This scene will be destroyed because it is local.
#         tmpScene = SomeScene()
#         tmpScene.destroyed.connect(self.onSceneDestroyed)

#         self.scene = SomeScene()
#         view = QtWidgets.QGraphicsView(self.scene)

#         hbox = QtWidgets.QHBoxLayout()
#         hbox.addWidget(view)

#         hbox.setMargin(0)
#         mainWidget = QtWidgets.QWidget()
#         mainWidget.setLayout(hbox)
#         # QtWidgets.QStatusBar(mainWidget)

#         self.setCentralWidget(mainWidget)
#         self.statusBar().showMessage('Proba')

#     def onSceneDestroyed(self, obj):
#         print('tmpScene destroyed')

# app = QtWidgets.QApplication(sys.argv)
# mainWindow = MainWindow()
# mainWindow.show()
# sys.exit(app.exec_())
