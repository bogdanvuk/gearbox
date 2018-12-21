from PySide2 import QtGui, QtCore, QtWidgets
from .node_abstract import AbstractNodeItem
from .port import PortItem

from .pipe import Pipe
from .constants import (IN_PORT, OUT_PORT, NODE_SEL_COLOR,
                        NODE_SEL_BORDER_COLOR, Z_VAL_NODE, Z_VAL_PIPE)

from pygears.core.port import InPort
from pygears.conf import reg_inject, Inject

import pygraphviz as pgv
from . import gv_utils
from grandalf.layouts import SugiyamaLayout
from grandalf.graphs import Vertex, Edge, Graph
from grandalf.routing import EdgeViewer


class defaultview:
    def __init__(self, w, h):
        self.w = h
        self.h = w


def inst_children(node):
    child_node_map = {}

    for child in node.model.child:

        graph_node = NodeItem(child, node)

        child_node_map[child] = graph_node

    for child, graph_node in child_node_map.items():
        child = graph_node.model

        if child.child:
            graph_node.collapse()

        for port in child.in_ports:
            producer = port.producer.producer

            if producer.gear is node.model:
                src_port = node.inputs[producer.index]
                dest_port = graph_node.inputs[port.index]
                node.connect(src_port, dest_port)

        for port in child.out_ports:
            for consumer in port.consumer.consumers:

                if consumer.gear is node.model:
                    consumer_graph_node = node
                else:
                    consumer_graph_node = child_node_map.get(consumer.gear)

                if consumer_graph_node:
                    src_port = graph_node.outputs[port.index]

                    if isinstance(consumer, InPort):
                        dest_port = consumer_graph_node.inputs[consumer.index]
                    else:
                        dest_port = consumer_graph_node.outputs[consumer.index]

                    node.connect(src_port, dest_port)

    return child_node_map


def hier_expand(node, padding=40):
    bound = node.node_bounding_rect

    print(bound)
    width, height = bound.width(), bound.height()

    if node.collapsed:
        if width < node.minimum_size[0]:
            width = node.minimum_size[0]

        if height < node.minimum_size[1]:
            height = node.minimum_size[1]

        node._width = width + padding * 2
        node._height = height + padding * 2
    else:
        node._width = width
        node._height = height + padding * 2

    node.post_init()

    # node.parent.layout()


def hier_painter(self, painter, option, widget):
    painter.save()

    rect = self.boundingRect()
    color = (self.color[0], self.color[1], self.color[2], 50)
    painter.setBrush(QtGui.QColor(*color))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawRect(rect)

    top_rect = QtCore.QRectF(0.0, 0.0, rect.width(), 20.0)
    painter.setBrush(QtGui.QColor(*self.color))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawRect(top_rect)

    if self.selected and NODE_SEL_COLOR:
        sel_color = [x for x in NODE_SEL_COLOR]
        sel_color[-1] = 10
        painter.setBrush(QtGui.QColor(*sel_color))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRect(rect)

    # txt_rect = QtCore.QRectF(top_rect.x(),
    #                          top_rect.y() + 1.5, rect.width(),
    #                          top_rect.height())
    # painter.setPen(QtGui.QColor(*self.text_color))
    # painter.drawText(txt_rect, QtCore.Qt.AlignCenter, self.name)

    path = QtGui.QPainterPath()
    path.addRect(rect)
    border_color = self.color
    if self.selected and NODE_SEL_BORDER_COLOR:
        border_color = NODE_SEL_BORDER_COLOR
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.setPen(QtGui.QPen(QtGui.QColor(*border_color), 1))
    painter.drawPath(path)

    # for port in self.inputs + self.outputs:
    #     for pipe in port.connected_pipes:
    #         pipe.draw_path()

    painter.restore()


def node_painter(self, painter, option, widget):
    painter.save()

    bg_border = 1.0
    rect = QtCore.QRectF(0.5 - (bg_border / 2), 0.5 - (bg_border / 2),
                         self._width + bg_border, self._height + bg_border)
    radius_x = 5
    radius_y = 5
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, radius_x, radius_y)
    painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 255), 1.5))
    painter.drawPath(path)

    rect = self.boundingRect()
    bg_color = QtGui.QColor(*self.color)
    painter.setBrush(bg_color)
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawRoundRect(rect, radius_x, radius_y)

    if self.selected and NODE_SEL_COLOR:
        painter.setBrush(QtGui.QColor(*NODE_SEL_COLOR))
        painter.drawRoundRect(rect, radius_x, radius_y)

    label_rect = QtCore.QRectF(rect.left() + (radius_x / 2),
                               rect.top() + (radius_x / 2),
                               self._width - (radius_x / 1.25), 28)
    path = QtGui.QPainterPath()
    path.addRoundedRect(label_rect, radius_x / 1.5, radius_y / 1.5)
    painter.setBrush(QtGui.QColor(0, 0, 0, 50))
    painter.fillPath(path, painter.brush())

    border_width = 0.8
    border_color = QtGui.QColor(*self.border_color)
    if self.selected and NODE_SEL_BORDER_COLOR:
        border_width = 1.2
        border_color = QtGui.QColor(*NODE_SEL_BORDER_COLOR)
    border_rect = QtCore.QRectF(rect.left() - (border_width / 2),
                                rect.top() - (border_width / 2),
                                rect.width() + border_width,
                                rect.height() + border_width)
    path = QtGui.QPainterPath()
    path.addRoundedRect(border_rect, radius_x, radius_y)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.setPen(QtGui.QPen(border_color, border_width))
    painter.drawPath(path)

    # for port in self.inputs + self.outputs:
    #     for pipe in port.connected_pipes:
    #         pipe.draw_path(pipe._input_port, pipe._output_port)

    painter.restore()


class NodeItem(AbstractNodeItem):
    @reg_inject
    def __init__(self, model, parent=None, graph=Inject('viewer/graph')):
        super().__init__(model.basename)

        self.parent = parent
        self.graph = graph
        self.layout_graph = pgv.AGraph(
            directed=True, rankdir='LR', splines='true', esep=1)

        self.layout_pipe_map = {}

        self._text_item = QtWidgets.QGraphicsTextItem(self.name, self)
        self._input_items = {}
        self._output_items = {}
        self._nodes = []
        self.pipes = []
        self.model = model
        self.minimum_size = (80, 80)

        self.layout_vertices = {}
        self.layout_root_vertices = []
        self.layout_edges = []
        self.layout_inport_vertices = {}
        self.layout_outport_vertices = {}

        if self.hierarchical:
            self.setZValue(Z_VAL_PIPE - 1)
            self.size_expander = hier_expand
            self.painter = hier_painter
        else:
            self.size_expander = lambda x: None
            self.painter = node_painter

        if parent is not None:
            for port in model.in_ports + model.out_ports:
                self._add_port(port)

        self._hide_single_port_labels()

        self.collapsed = False if parent is None else True
        self.collapsed_size = self.calc_size()
        self._width, self._height = self.collapsed_size

        self.post_init()

        self.layers = []

        # First add node to the scene, so that all pipes can be rendered in the
        # inst_children() procedure
        if self.parent is not None:
            self.parent.add_node(self)

        self.child_node_map = inst_children(self)

        if parent is not None:
            for node in self._nodes:
                node.hide()

    def mouseDoubleClickEvent(self, event):
        self.auto_resize()

    # def mousePressEvent(self, event):
    #     if event.button() == QtCore.Qt.MouseButton.LeftButton:
    #         pos = event.scenePos()
    #         rect = QtCore.QRectF(pos.x() - 5, pos.y() - 5, 10, 10)
    #         item = self.scene().items(rect)[0]

    #         # if isinstance(item, (PortItem, Pipe)):
    #         #     self.setFlag(self.ItemIsMovable, False)
    #         #     return
    #         # if self.selected:
    #         #     return

    #         self.selected = True

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # self.setFlag(self.ItemIsMovable, True)
        self.selected = True

    @property
    def hierarchical(self):
        return bool(self.model.child)

    def auto_resize(self, nodes=None):
        if self.collapsed:
            self.expand()
        else:
            self.collapse()

    def paint(self, painter, option, widget):
        self.painter(self, painter, option, widget)

    def hide(self):
        for obj in self.children:
            obj.hide()

        super().hide()

    def show(self):
        super().show()
        ports = self.inputs + self.outputs
        for port in ports:
            for pipe in port.connected_pipes:
                if pipe.input_port.isVisible() and pipe.output_port.isVisible(
                ):
                    pipe.show()

    def collapse(self):
        if self.collapsed or not self.hierarchical:
            return

        print(f'Collapsing: {self.model.name}')
        for obj in self.children:
            obj.hide()

        self.collapsed = True
        self.graph.top.layout()

    def expand(self):
        if not self.collapsed or not self.hierarchical:
            return None

        print(f'Expanding: {self.model.name}')

        for obj in self.children:
            obj.show()

        self.collapsed = False
        self.show()
        self.graph.top.layout()
        self.selected = True

    def get_visible_objs(self, objtype):
        for n in self._nodes:
            if (objtype is None) or (objtype is NodeItem):
                yield n

            if not n.collapsed:
                yield from n.get_visible_objs(objtype)

        if (objtype is None) or (objtype is Pipe):
            for p in self.pipes:
                yield p

    def set_pos(self, x=0.0, y=0.0):
        self.setPos(x, y)
        # print(f'Pos {self.model.name}: {self.pos}')
        # if not self.hierarchical:
        #     return

        # padding = 40
        # x_min = min(
        #     v.view.xy[1] - v.view.h / 2 for v in self.layout_vertices.values())

        # y_min = min(
        #     v.view.xy[0] - v.view.w / 2 for v in self.layout_vertices.values())

        # for n, v in self.layout_vertices.items():
        #     # n.set_pos(x + v.view.xy[1] - x_min - v.view.h / 2 + padding,
        #     #           y + v.view.xy[0] - y_min - v.view.w / 2 + padding)
        #     # n.set_pos(v.view.xy[1] - x_min - v.view.h / 2 + padding,
        #     #           v.view.xy[0] - y_min - v.view.w / 2 + padding)
        #     n.set_pos(v.view.xy[1] - x_min - v.view.h / 2 + padding,
        #               v.view.xy[0] - y_min - v.view.w / 2 + padding)

    def _hide_single_port_labels(self):
        for port, text in self._input_items.items():
            if len(self._input_items) == 1:
                text.setVisible(False)

        for port, text in self._output_items.items():
            if len(self._output_items) == 1:
                text.setVisible(False)

    def _add_port(self, port, display_name=True):
        port_item = PortItem(port, self)
        port_item.display_name = display_name
        text = QtWidgets.QGraphicsTextItem(port_item.name, self)
        text.font().setPointSize(8)
        text.setFont(text.font())
        # text.setVisible(display_name)

        if isinstance(port, InPort):
            self.layout_graph.add_node(
                f'i{len(self._input_items)}',
                label='',
                rank='source',
                width=2 / 72,
                height=2 / 72)
            self._input_items[port_item] = text
        else:
            self.layout_graph.add_node(
                f'o{len(self._output_items)}',
                label='',
                rank='sink',
                width=2 / 72,
                height=2 / 72)

            self._output_items[port_item] = text

        return port_item

    @AbstractNodeItem.selected.setter
    def selected(self, selected=False):
        AbstractNodeItem.selected.fset(self, selected)
        # for n in self._nodes:
        #     n.selected = selected

        if selected:
            self.hightlight_pipes()

    @AbstractNodeItem.name.setter
    def name(self, name=''):
        AbstractNodeItem.name.fset(self, name)
        self._text_item.setPlainText(name)
        if self.scene():
            self.post_init()

    @property
    def inputs(self):
        return list(self._input_items.keys())

    @property
    def outputs(self):
        return list(self._output_items.keys())

    @AbstractNodeItem.width.setter
    def width(self, width=0.0):
        w, h = self.calc_size()
        # self._width = width if width > w else w
        width = width if width > w else w
        AbstractNodeItem.width.fset(self, width)

    @AbstractNodeItem.height.setter
    def height(self, height=0.0):
        w, h = self.calc_size()
        h = 70 if h < 70 else h
        # self._height = height if height > h else h
        height = height if height > h else h
        AbstractNodeItem.height.fset(self, height)

    @AbstractNodeItem.disabled.setter
    def disabled(self, state=False):
        AbstractNodeItem.disabled.fset(self, state)
        for n, w in self._widgets.items():
            w.widget.setDisabled(state)
        self._tooltip_disable(state)
        self._x_item.setVisible(state)

    def itemChange(self, change, value):
        if change == self.ItemSelectedChange and self.scene():
            self.reset_pipes()
            if value:
                self.hightlight_pipes()
            self.setZValue(Z_VAL_NODE)
            if not self.selected:
                self.setZValue(Z_VAL_NODE + 1)

        return super(NodeItem, self).itemChange(change, value)

    def _tooltip_disable(self, state):
        tooltip = '<b>{}</b>'.format(self._properties['name'])
        if state:
            tooltip += ' <font color="red"><b>(DISABLED)</b></font>'
        tooltip += '<br/>{}<br/>'.format(self._properties['type'])
        self.setToolTip(tooltip)

    def _set_text_color(self, color):
        """
        set text color.

        Args:
            color (tuple): color value in (r, g, b, a).
        """
        text_color = QtGui.QColor(*color)
        for port, text in self._input_items.items():
            text.setDefaultTextColor(text_color)
        for port, text in self._output_items.items():
            text.setDefaultTextColor(text_color)
        self._text_item.setDefaultTextColor(text_color)

    def activate_pipes(self):
        """
        active pipe color.
        """
        ports = self.inputs + self.outputs
        for port in ports:
            for pipe in port.connected_pipes:
                pipe.activate()

    def hightlight_pipes(self):
        """
        highlight pipe color.
        """
        ports = self.inputs + self.outputs
        for port in ports:
            for pipe in port.connected_pipes:
                pipe.highlight()

    def reset_pipes(self):
        """
        reset the pipe color.
        """
        ports = self.inputs + self.outputs
        for port in ports:
            for pipe in port.connected_pipes:
                pipe.reset()

    def calc_size(self):
        """
        calculate minimum node size.
        """
        width = 0.0
        if self._text_item.boundingRect().width() > width:
            width = self._text_item.boundingRect().width()

        port_height = 0.0
        if self._input_items:
            input_widths = []
            for port, text in self._input_items.items():
                input_width = port.boundingRect().width() * 2
                if text.isVisible():
                    input_width += text.boundingRect().width()
                input_widths.append(input_width)
            width += max(input_widths)
            port = list(self._input_items.keys())[0]
            port_height = port.boundingRect().height() * 2
        if self._output_items:
            output_widths = []
            for port, text in self._output_items.items():
                output_width = port.boundingRect().width() * 2
                if text.isVisible():
                    output_width += text.boundingRect().width()
                output_widths.append(output_width)
            width += max(output_widths)
            port = list(self._output_items.keys())[0]
            port_height = port.boundingRect().height() * 2

        height = port_height * (max([len(self.inputs), len(self.outputs)]) + 2)
        height += 10

        print(f'Size {self.model.name}: {width}, {height}')
        return width, height

    def arrange_label(self):
        """
        Arrange node label to the default top center of the node.
        """
        text_rect = self._text_item.boundingRect()
        text_x = (self._width / 2) - (text_rect.width() / 2)
        self._text_item.setPos(text_x, -3.0)

    def arrange_ports(self, padding_x=0.0, padding_y=0.0):
        """
        Arrange input, output ports in the node layout.

        Args:
            padding_x (float): horizontal padding.
            padding_y: (float): vertical padding.
        """
        width = self._width - padding_x
        height = self._height - padding_y

        # adjust input position
        if self.collapsed and self.inputs:
            port_width = self.inputs[0].boundingRect().width()
            port_height = self.inputs[0].boundingRect().height()
            chunk = (height / len(self.inputs))
            port_x = (port_width / 2) * -1
            port_y = (chunk / 2) - (port_height / 2)
            # for port in self.inputs:
            for i, p in enumerate(self.inputs):
                p.setPos(port_x + padding_x, port_y + (padding_y / 2) + 15)
                port_y += chunk

        # adjust input text position
        for port, text in self._input_items.items():
            txt_height = text.boundingRect().height() - 8.0
            txt_x = port.x() + port.boundingRect().width()
            txt_y = port.y() - (txt_height / 2)
            text.setPos(txt_x + 3.0, txt_y)

        # adjust output position
        if self.collapsed and self.outputs:
            port_width = self.outputs[0].boundingRect().width()
            port_height = self.outputs[0].boundingRect().height()
            chunk = height / len(self.outputs)
            port_x = width - (port_width / 2)
            port_y = (chunk / 2) - (port_height / 2)
            # for port in self.outputs:

            for i, p in enumerate(self.outputs):
                p.setPos(port_x, port_y + (padding_y / 2) + 15)
                port_y += chunk

        # adjust output text position
        for port, text in self._output_items.items():
            txt_width = text.boundingRect().width()
            txt_height = text.boundingRect().height() - 8.0
            txt_x = width - txt_width - (port.boundingRect().width() / 2)
            txt_y = port.y() - (txt_height / 2)
            text.setPos(txt_x - 1.0, txt_y)

    def offset_label(self, x=0.0, y=0.0):
        """
        offset the label in the node layout.

        Args:
            x (float): horizontal x offset
            y (float): vertical y offset
        """
        icon_x = self._text_item.pos().x() + x
        icon_y = self._text_item.pos().y() + y
        self._text_item.setPos(icon_x, icon_y)

    def offset_ports(self, x=0.0, y=0.0):
        """
        offset the ports in the node layout.

        Args:
            x (float): horizontal x offset
            y (float): vertical y offset
        """
        for port, text in self._input_items.items():
            port_x, port_y = port.pos().x(), port.pos().y()
            text_x, text_y = text.pos().x(), text.pos().y()
            port.setPos(port_x + x, port_y + y)
            text.setPos(text_x + x, text_y + y)
        for port, text in self._output_items.items():
            port_x, port_y = port.pos().x(), port.pos().y()
            text_x, text_y = text.pos().x(), text.pos().y()
            port.setPos(port_x + x, port_y + y)
            text.setPos(text_x + x, text_y + y)

    def post_init(self, viewer=None, pos=None):
        """
        Called after node has been added into the scene.
        Adjust the node layout and form after the node has been added.

        Args:
            viewer (NodeGraphQt.widgets.viewer.NodeViewer): not used
            pos (tuple): cursor position.
        """
        # set initial node position.
        if pos:
            self.setPos(pos[0], pos[1])

        # set text color when node is initialized.
        self._set_text_color(self.text_color)
        # set the tooltip
        self._tooltip_disable(self.disabled)

        # setup node layout
        # =================

        # arrange label text
        self.arrange_label()
        self.offset_label(0.0, 5.0)

        # arrange input and output ports.
        self.arrange_ports(padding_y=35.0)
        # self.offset_ports(0.0, 15.0)

        for p in self.pipes:
            if not self.collapsed:
                p.draw_path()

    @property
    def children(self):
        return self._nodes + self.pipes

    def add_node(self, node):
        if self.parent is not None:
            node.setParentItem(self)
        else:
            self.graph.add_node(node, node.pos())

        node.update()

        self.layout_graph.add_node(id(node), shape='none', margin=0)

        self._nodes.append(node)

    def connect(self, port1, port2):
        node1 = port1.node
        node2 = port2.node

        pipe = Pipe(port1, port2)
        if self.parent is not None:
            pipe.setParentItem(self)
        else:
            self.graph.scene().addItem(pipe)

        self.pipes.append(pipe)

        if (node2 is not self) and (node1 is not self):
            self.layout_graph.add_edge(
                id(node1),
                id(node2),
                tailport=f'o{pipe.output_port.model.index}',
                headport=f'i{pipe.input_port.model.index}',
                key=id(pipe))
        elif (node2 is self):
            self.layout_graph.add_edge(
                id(node1),
                f'o{pipe.input_port.model.index}',
                tailport=f'o{pipe.output_port.model.index}',
                key=id(pipe))
        else:
            self.layout_graph.add_edge(
                f'i{pipe.input_port.model.index}',
                id(node2),
                headport=f'i{pipe.input_port.model.index}',
                key=id(pipe))

    @property
    def node_bounding_rect(self):
        bound = QtCore.QRectF()
        for n in self._nodes:
            br = n.boundingRect()
            br.translate(n.x(), n.y())
            bound = bound.united(br)

        if not self.collapsed:
            for p in self.inputs:
                br = p.boundingRect()
                br.translate(p.x() + br.width() / 2, p.y())
                bound = bound.united(br)

            for p in self.outputs:
                br = p.boundingRect()
                br.translate(p.x() - br.width() / 2, p.y())
                bound = bound.united(br)

        return bound

    def get_layout_edge(self, pipe):
        node1 = pipe.output_port.node
        node2 = pipe.input_port.node

        if node1 is self:
            node1_id = f'i{pipe.input_port.model.index}'
        else:
            node1_id = id(node1)

        if node2 is self:
            node2_id = f'o{pipe.input_port.model.index}'
        else:
            node2_id = id(node2)

        return self.layout_graph.get_edge(node1_id, node2_id, id(pipe))

    def get_layout_node(self, node):
        return self.layout_graph.get_node(str(id(node)))

    def layout(self):
        print(f'Laying out {self.model.name}')
        if not self.hierarchical:
            return

        if self.collapsed:
            self._width, self._height = self.collapsed_size
            self.post_init()
            return

        for node in self._nodes:
            if hasattr(node, 'layout'):
                node.layout()

        for node in self._nodes:
            gvn = self.get_layout_node(node)
            gvn.attr['label'] = gv_utils.get_node_record(node).replace(
                '\n', '')

        # for i in range(len(self.inputs)):
        #     gvn = self.layout_graph.get_node(f'i{i}')

        # for i in range(len(self.outputs)):
        #     gvn = self.layout_graph.get_node(f'o{i}')

        # for pipe in self.pipes:
        #     gve = self.get_layout_edge(pipe)

        print(self.model.name)
        self.layout_graph.layout(prog='dot')
        if self.model.name == '':
            self.layout_graph.draw('proba.png')
            self.layout_graph.draw('proba.dot')
        else:
            self.layout_graph.draw(f'{self.model.name.replace("/", "_")}.png')
            self.layout_graph.draw(f'{self.model.name.replace("/", "_")}.dot')

        # if self.model.name == '/ref_model':
        #     self.layout_graph.draw('proba.dot')

        # all_vertices = {**self.layout_vertices, **all_port_vertices}
        # g = Graph(list(all_vertices.values()), self.layout_edges)

        # for node, v in self.layout_vertices.items():
        #     if hasattr(node, 'layout'):
        #         node.layout()
        #     v.view = defaultview(node.width, node.height)

        # # sug = DigcoLayout(g.C[0])
        # sug = SugiyamaLayout(g.C[0])

        # # sug.init_all(roots=self.layout_dummy_vertices[0:1])
        # sug.init_all(optimize=True)
        # # sug.xspace = 20
        # sug.yspace = 50

        # # sug.route_edge = route_with_rounded_corners
        # sug.draw(5)
        # sug.draw_edges()

        # for v in self.layout_dummy_vertices:
        #     print(vars(v.view))

        # self.layers = []
        # for layer in sug.layers:
        #     layer = [
        #         v.data for v in layer if getattr(v, 'data', None) and (
        #             not isinstance(v.data, PortItem))
        #     ]
        #     if layer:
        #         self.layers.append(layer)

        # padding = 40
        # x_min = min(
        #     v.view.xy[1] - v.view.h / 2 for v in self.layout_vertices.values())

        # y_min = min(
        #     v.view.xy[0] - v.view.w / 2 for v in self.layout_vertices.values())

        # for n, v in self.layout_vertices.items():
        #     n.set_pos(v.view.xy[1] - x_min - v.view.h / 2 + padding,
        #               v.view.xy[0] - y_min - v.view.w / 2 + padding)

        # for n, v in all_port_vertices.items():
        #     v.view.xy = (v.view.xy[1] - x_min + padding,
        #                  v.view.xy[0] - y_min + padding)

        def gv_point_load(point):
            return tuple(float(num) for num in point.split(',')[-2:])

        padding = 40
        max_y = 0
        max_x = 0

        # if self.model.name == '/ref_model':
        #     import pdb
        #     pdb.set_trace()

        for node in self._nodes:
            gvn = self.get_layout_node(node)
            pos = gv_point_load(gvn.attr['pos'])
            node.set_pos(pos[0] - node.width / 2, pos[1] + node.height / 2)

            if self.outputs:
                self.layout_graph.add_edge(
                    gvn, self.layout_graph.get_node(f'o0'), style='invis')

            max_y = max(max_y, (pos[1] + node.height / 2))
            max_x = max(max_x, (pos[0] + node.width / 2))

        if self.inputs:
            port_height = self.inputs[0].boundingRect().height()

            for i, p in enumerate(self.inputs):
                gvn = self.layout_graph.get_node(f'i{i}')
                pos = gv_point_load(gvn.attr['pos'])

                p.setPos(-port_height / 2, pos[1] + port_height / 2)

        if self.outputs:
            port_height = self.outputs[0].boundingRect().height()

            for i, p in enumerate(self.outputs):
                gvn = self.layout_graph.get_node(f'o{i}')
                pos = gv_point_load(gvn.attr['pos'])

                p.setPos(pos[0] - port_height / 2, pos[1] + port_height / 2)

        for pipe in self.pipes:
            gve = self.get_layout_edge(pipe)
            path = [gv_point_load(point) for point in gve.attr['pos'].split()]
            pipe.layout_path = [QtCore.QPointF(p[0], p[1]) for p in path]

            max_y = max(max_y, *(p.y() for p in pipe.layout_path))

        for node in self._nodes:
            node.setY(max_y - node.y() + padding)

        for p in self.inputs:
            p.setY(max_y - p.y() + padding)

        for p in self.outputs:
            p.setY(max_y - p.y() + padding)
            if p.x() <= max_x:
                p.setX(max_x + padding)

        for pipe in self.pipes:
            for p in pipe.layout_path:
                p.setY(max_y - p.y() + padding)

        # for edge in self.layout_edges:
        #     if not hasattr(edge, 'view'):
        #         continue

        #     pipe = edge.data

        #     pipe.layout_path = [
        #         QtCore.QPointF(p[1] - x_min + padding, p[0] - y_min + padding)
        #         for p in reversed(edge.view._pts[1:-1])
        #     ]

        self.size_expander(self)
