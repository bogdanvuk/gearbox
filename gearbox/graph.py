#!/usr/bin/python

from PySide2 import QtCore, QtWidgets, QtGui
import warnings

from .constants import (IN_PORT, OUT_PORT, PIPE_LAYOUT_CURVED,
                        PIPE_LAYOUT_STRAIGHT, PIPE_DEFAULT_COLOR)

from .node_abstract import AbstractNodeItem
from .pipe import Pipe
from .port import PortItem
from .scene import NodeScene
from .node import NodeItem
from .node_model import NodeModel
from .layout import Buffer, LayoutPlugin
from .html_utils import tabulate, fontify
from .utils import single_shot_connect

from pygears.conf import Inject, inject, MayInject, reg

ZOOM_MIN = -0.95
ZOOM_MAX = 2.0

PIPE_WAITED_COLOR = (13, 232, 184, 255)
PIPE_ACTIVE_COLOR = (232, 13, 184, 255)


class GraphVisitor:
    def visit(self, node):
        self.node(node)

    def node(self, node):
        for pipe in node.pipes:
            self.pipe(pipe)

        for node in node._nodes:
            self.node(node)

    def pipe(self):
        pass


class GraphBuffer(Buffer):
    @property
    def domain(self):
        return 'graph'


@inject
def graph(
        sim_bridge=Inject('gearbox/sim_bridge'),
        root=Inject('gear/root')):

    reg['gearbox/graph_model_ctrl'] = GraphModelCtrl()


# def graph_delete():
#     bind('gearbox/graph', None)
#     bind('gearbox/graph_model', None)


# @inject
# def graph_create(
#         root=Inject('gear/root'),
#         sim_bridge=Inject('gearbox/sim_bridge')):

#     view = Graph()
#     single_shot_connect(sim_bridge.model_closed, graph_delete)

#     bind('gearbox/graph', view)
#     root = rtlgen(root, force=True)
#     top_model = NodeModel(root)
#     bind('gearbox/graph_model', top_model)
#     view.top = top_model.view
#     top_model.view.layout()
#     view.fit_all()

#     buff = GraphBuffer(view, 'graph')
#     single_shot_connect(sim_bridge.model_closed, buff.delete)

#     return buff

class GraphModelCtrl(QtCore.QObject):
    model_loaded = QtCore.Signal()
    working_model_loaded = QtCore.Signal()

    @inject
    def __init__(self, sim_bridge=Inject('gearbox/sim_bridge')):
        super().__init__()
        self.sim_bridge = sim_bridge
        self.sim_bridge.model_loaded.connect(self.graph_create)
        self.sim_bridge.before_run.connect(self.graph_create)
        self.sim_bridge.model_closed.connect(self.graph_delete)

    @inject
    def graph_create(self, root=Inject('gear/root')):
        view = Graph()

        reg['gearbox/graph'] = view
        top_model = NodeModel(root)
        reg['gearbox/graph_model'] = top_model
        view.top = top_model.view
        top_model.view.layout()
        view.fit_all()

        self.buff = GraphBuffer(view, 'graph')

        self.model_loaded.emit()

        if not self.err:
            self.working_model_loaded.emit()

        return self.buff

    @property
    def err(self):
        return self.sim_bridge.err

    def graph_delete(self):
        self.buff.delete()
        del self.buff
        reg['gearbox/graph'] = None
        reg['gearbox/graph_model'] = None


class Graph(QtWidgets.QGraphicsView):

    moved_nodes = QtCore.Signal(dict)
    connection_changed = QtCore.Signal(list, list)
    selection_changed = QtCore.Signal(list)
    node_selected = QtCore.Signal(str)
    resized = QtCore.Signal()
    node_expand_toggled = QtCore.Signal(bool, object)

    @inject
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(NodeScene(self))
        self.scene().selectionChanged.connect(self.selection_changed_slot)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self._pipe_layout = PIPE_LAYOUT_STRAIGHT
        self._live_pipe = None
        self._detached_port = None
        self._start_port = None
        self._origin_pos = None
        self._previous_pos = QtCore.QPoint(self.width(), self.height())
        self._prev_selection = []
        self._node_positions = {}
        self._rubber_band = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Rectangle, self)
        self._undo_stack = QtWidgets.QUndoStack(self)
        warnings.filterwarnings(
            'ignore', '.*cell size too small for content.*', RuntimeWarning)

        self.acyclic = True
        self.LMB_state = False
        self.RMB_state = False
        self.MMB_state = False

    def __str__(self):
        return '{}.{}()'.format(self.__module__, self.__class__.__name__)

    def __repr__(self):
        return '{}.{}()'.format(self.__module__, self.__class__.__name__)

    def _set_viewer_zoom(self, value):
        if value == 0.0:
            return
        scale = 0.9 if value < 0.0 else 1.1
        zoom = self.get_zoom()
        if ZOOM_MIN >= zoom:
            if scale == 0.9:
                return
        if ZOOM_MAX <= zoom:
            if scale == 1.1:
                return
        self.scale(scale, scale)

    def _set_viewer_pan(self, pos_x, pos_y):
        scroll_x = self.horizontalScrollBar()
        scroll_y = self.verticalScrollBar()
        scroll_x.setValue(scroll_x.value() - pos_x)
        scroll_y.setValue(scroll_y.value() - pos_y)

    def _combined_rect(self, nodes):
        group = self.scene().createItemGroup(nodes)
        rect = group.boundingRect()
        self.scene().destroyItemGroup(group)
        return rect

    def _items_near(self, pos, item_type=None, width=20, height=20):
        x, y = pos.x() - width, pos.y() - height
        rect = QtCore.QRect(x, y, width, height)
        items = []
        for item in self.scene().items(rect):
            if not item_type or isinstance(item, item_type):
                items.append(item)
        return items

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return

        alt_modifier = event.modifiers() == QtCore.Qt.AltModifier
        shift_modifier = event.modifiers() == QtCore.Qt.ShiftModifier
        if event.button() == QtCore.Qt.LeftButton:
            self.LMB_state = True
        elif event.button() == QtCore.Qt.RightButton:
            self.RMB_state = True
        elif event.button() == QtCore.Qt.MiddleButton:
            self.MMB_state = True
        self._origin_pos = event.pos()
        self._previous_pos = event.pos()
        self._prev_selection = self.selected_nodes()

        if alt_modifier:
            return

        items = self._items_near(self.mapToScene(event.pos()), None, 20, 20)
        nodes = [i for i in items if isinstance(i, AbstractNodeItem)]

        # toggle extend node selection.
        if shift_modifier:
            for node in nodes:
                node.selected = not node.selected

        # update the recorded node positions.
        self._node_positions.update({n: n.pos for n in self.selected_nodes()})

        # show selection selection marquee
        if self.LMB_state and not items:
            rect = QtCore.QRect(self._previous_pos, QtCore.QSize())
            rect = rect.normalized()
            map_rect = self.mapToScene(rect).boundingRect()
            self.scene().update(map_rect)
            self._rubber_band.setGeometry(rect)
            self._rubber_band.show()

        if not shift_modifier:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.LMB_state = False
        elif event.button() == QtCore.Qt.RightButton:
            self.RMB_state = False
        elif event.button() == QtCore.Qt.MiddleButton:
            self.MMB_state = False

        # hide selection marquee
        if self._rubber_band.isVisible():
            rect = self._rubber_band.rect()
            map_rect = self.mapToScene(rect).boundingRect()
            self._rubber_band.hide()
            self.scene().update(map_rect)

        # find position changed nodes and emit signal.
        moved_nodes = {
            n: pos
            for n, pos in self._node_positions.items() if n.pos != pos
        }
        if moved_nodes:
            self.moved_nodes.emit(moved_nodes)

        # reset recorded positions.
        self._node_positions = {}

        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        alt_modifier = event.modifiers() == QtCore.Qt.AltModifier
        shift_modifier = event.modifiers() == QtCore.Qt.ShiftModifier
        if self.MMB_state and alt_modifier:
            pos_x = (event.x() - self._previous_pos.x())
            zoom = 0.1 if pos_x > 0 else -0.1
            self._set_viewer_zoom(zoom)
        elif self.MMB_state or (self.LMB_state and alt_modifier):
            pos_x = (event.x() - self._previous_pos.x())
            pos_y = (event.y() - self._previous_pos.y())
            self._set_viewer_pan(pos_x, pos_y)

        if self.LMB_state and self._rubber_band.isVisible():
            rect = QtCore.QRect(self._origin_pos, event.pos()).normalized()
            map_rect = self.mapToScene(rect).boundingRect()
            path = QtGui.QPainterPath()
            path.addRect(map_rect)
            self._rubber_band.setGeometry(rect)
            self.scene().setSelectionArea(path, QtCore.Qt.IntersectsItemShape)
            self.scene().update(map_rect)

            if shift_modifier and self._prev_selection:
                for node in self._prev_selection:
                    if node not in self.selected_nodes():
                        node.selected = True

        self._previous_pos = event.pos()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        adjust = (event.delta() / 120) * 0.1
        self._set_viewer_zoom(adjust)

    def all_pipes(self):
        pipes = []
        for item in self.scene().items():
            if isinstance(item, Pipe):
                pipes.append(item)
        return pipes

    def selection_changed_slot(self):
        self.selection_changed.emit(self.selected_items())

    def select(self, obj):

        for n in self.selected_nodes():
            n.selected = False

        for p in self.selected_pipes():
            p.setSelected(False)

        obj.setSelected(True)
        self.ensureVisible(obj)

        # print("Selection changed!")
        # self.selection_changed.emit(self.selected_items())

    def select_all(self):
        """
        Select all nodes in the current node graph.
        """
        self._undo_stack.beginMacro('select all')
        for node in self.all_nodes():
            node.set_selected(True)
        self._undo_stack.endMacro()

    def clear_selection(self):
        """
        Clears the selection in the node graph.
        """
        self._undo_stack.beginMacro('deselected nodes')
        for node in self.all_nodes():
            node.set_selected(False)
        self._undo_stack.endMacro()

    def all_nodes(self):
        nodes = []
        for item in self.scene().items():
            if isinstance(item, AbstractNodeItem):
                nodes.append(item)
        return nodes

    def selected_nodes(self):
        nodes = []
        for item in self.scene().selectedItems():
            if isinstance(item, AbstractNodeItem):
                nodes.append(item)
        return nodes

    def selected_pipes(self):
        pipes = []
        for item in self.scene().selectedItems():
            if isinstance(item, Pipe):
                pipes.append(item)
        return pipes

    def selected_items(self):
        return self.selected_nodes() + self.selected_pipes()

    def add_node(self, node, pos=None):
        pos = pos or (self._previous_pos.x(), self._previous_pos.y())
        node.pre_init(self, pos)
        self.scene().addItem(node)

    def remove_node(self, node):
        if isinstance(node, AbstractNodeItem):
            node.delete()

    def move_nodes(self, nodes, pos=None, offset=None):
        group = self.scene().createItemGroup(nodes)
        group_rect = group.boundingRect()
        if pos:
            x, y = pos
        else:
            pos = self.mapToScene(self._previous_pos)
            x = pos.x() - group_rect.center().x()
            y = pos.y() - group_rect.center().y()
        if offset:
            x += offset[0]
            y += offset[1]
        group.setPos(x, y)
        self.scene().destroyItemGroup(group)

    def get_pipes_from_nodes(self, nodes=None):
        nodes = nodes or self.selected_nodes()
        if not nodes:
            return
        pipes = []
        for node in nodes:
            n_inputs = node.inputs if hasattr(node, 'inputs') else []
            n_outputs = node.outputs if hasattr(node, 'outputs') else []

            for port in n_inputs:
                for pipe in port.connected_pipes:
                    connected_node = pipe.output_port.node
                    if connected_node in nodes:
                        pipes.append(pipe)
            for port in n_outputs:
                for pipe in port.connected_pipes:
                    connected_node = pipe.input_port.node
                    if connected_node in nodes:
                        pipes.append(pipe)
        return pipes

    def center_on(self, nodes=None):
        """
        Center the node graph on the given nodes or all nodes by default.

        Args:
            nodes (list[NodeGraphQt.Node]): a list of nodes.
        """
        self.center_selection(nodes)

    def center_selection(self, nodes=None):
        if not nodes:
            if self.selected_nodes():
                nodes = self.selected_nodes()
            elif self.all_nodes():
                nodes = self.all_nodes()
        if len(nodes) == 1:
            self.centerOn(nodes[0])
        else:
            rect = self._combined_rect(nodes)
            self.centerOn(rect.center().x(), rect.center().y())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    def get_pipe_layout(self):
        return self._pipe_layout

    def set_pipe_layout(self, layout=''):
        layout_types = {
            'curved': PIPE_LAYOUT_CURVED,
            'straight': PIPE_LAYOUT_STRAIGHT
        }
        self._pipe_layout = layout_types.get(layout, 'curved')
        # for pipe in self.all_pipes():
        #     pipe.draw_path(pipe.input_port, pipe.output_port)

    def reset_zoom(self):
        self.scale(1.0, 1.0)
        self.resetMatrix()

    def get_zoom(self):
        transform = self.transform()
        cur_scale = (transform.m11(), transform.m22())
        return float('{:0.2f}'.format(cur_scale[0] - 1.0))

    def set_zoom(self, value=0.0):
        if value == 0.0:
            self.reset_zoom()
            return
        zoom = self.get_zoom()
        if zoom < 0.0:
            if not (ZOOM_MIN <= zoom <= ZOOM_MAX):
                return
        else:
            if not (ZOOM_MIN <= value <= ZOOM_MAX):
                return
        value = value - zoom
        self._set_viewer_zoom(value)

    def fit_all(self):
        self.zoom_to_nodes(self.top._nodes)

    def zoom_to_nodes(self, nodes):
        from functools import reduce

        def box(node):
            return node.sceneBoundingRect()

        rect = reduce(lambda x, y: x.united(y), map(box, nodes))
        self.fitInView(rect, QtCore.Qt.KeepAspectRatio)

        if self.get_zoom() > 0.1:
            self.reset_zoom()


class GraphBufferPlugin(LayoutPlugin):
    @classmethod
    def bind(cls):
        reg['gearbox/plugins/graph'] = {}
