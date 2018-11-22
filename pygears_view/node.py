from PySide2 import QtGui, QtCore
from .node_abstract import AbstractNodeItem
from .port import PortItem

from .constants import (IN_PORT, OUT_PORT, NODE_ICON_SIZE, ICON_NODE_BASE,
                        NODE_SEL_COLOR, NODE_SEL_BORDER_COLOR, Z_VAL_NODE,
                        Z_VAL_NODE_WIDGET, Z_VAL_PIPE)

from PySide2.QtWidgets import (QGraphicsItem, QGraphicsPixmapItem,
                               QGraphicsTextItem)

from pygears.core.port import InPort

from grandalf.layouts import SugiyamaLayout
from grandalf.graphs import Vertex, Edge, Graph


def inst_children(node, graph):
    child_node_map = {}

    for child in node.model.child:

        graph_node = NodeItem(child, graph, node)

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
                    if isinstance(consumer, InPort):
                        src_port = graph_node.outputs[port.index]
                        dest_port = consumer_graph_node.inputs[consumer.index]
                    else:
                        src_port = consumer_graph_node.outputs[consumer.index]
                        dest_port = graph_node.outputs[port.index]

                    node.connect(src_port, dest_port)

    return child_node_map


def hier_expand(node, padding=40):
    def _combined_rect(node):
        group = node.scene().createItemGroup(node._nodes)
        rect = group.boundingRect()
        node.scene().destroyItemGroup(group)
        return rect

    node._prev_size = (node.width, node.height)

    nodes_rect = _combined_rect(node)

    width, height = nodes_rect.width(), nodes_rect.height()
    if width < node.minimum_size[0]:
        width = node.minimum_size[0]

    if height < node.minimum_size[1]:
        height = node.minimum_size[1]

    node._width = width + padding * 2
    node._height = height + padding * 2
    node.post_init()

    node.parent.layout()


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

    for port in self.inputs + self.outputs:
        for pipe in port.connected_pipes:
            pipe.draw_path(pipe._input_port, pipe._output_port)

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

    for port in self.inputs + self.outputs:
        for pipe in port.connected_pipes:
            pipe.draw_path(pipe._input_port, pipe._output_port)

    painter.restore()


class NodeItem(AbstractNodeItem):
    def __init__(self, model, graph, parent=None):
        super().__init__(model.basename, parent)

        self.parent = parent
        self.graph = graph
        self._text_item = QGraphicsTextItem(self.name, self)
        self._input_items = {}
        self._output_items = {}
        self._nodes = []
        self.model = model
        self.minimum_size = (80, 80)
        self._prev_size = None

        self.layout_vertices = {}
        self.layout_root_vertices = []
        self.layout_edges = []

        if self.hierarchical:
            self.setZValue(Z_VAL_PIPE - 1)
            self.size_expander = hier_expand
            self.painter = hier_painter
        else:
            self.size_expander = lambda x: None
            self.painter = node_painter

        if not model.root() == model:
            for port in model.in_ports + model.out_ports:
                self._add_port(port)

        # First add node to the scene, so that all pipes can be rendered in the
        # inst_children() procedure
        if not model.root() == model:
            self.graph.viewer().add_node(self, self.pos)

        self.child_node_map = inst_children(self, graph)

        if self.parent is not None:
            self.parent.add_node(self)

        if not model.root() == model:
            for node in self._nodes:
                node.hide()

    def mouseDoubleClickEvent(self, event):
        self.auto_resize()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            rect = QtCore.QRectF(pos.x() - 5, pos.y() - 5, 10, 10)
            item = self.scene().items(rect)[0]

            # if isinstance(item, (PortItem, Pipe)):
            #     self.setFlag(self.ItemIsMovable, False)
            #     return
            # if self.selected:
            #     return

            [n.setSelected(True) for n in self._nodes]
            self.setSelected(True)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setFlag(self.ItemIsMovable, True)
        [n.setSelected(True) for n in self._nodes]
        self.setSelected(True)

    @property
    def hierarchical(self):
        return bool(self.model.child)

    @property
    def collapsed(self):
        return not bool(self._prev_size)

    def auto_resize(self, nodes=None):
        if self._prev_size:
            self.collapse()
        else:
            self.expand()

    def paint(self, painter, option, widget):
        self.painter(self, painter, option, widget)

    def hide(self):
        ports = self.inputs + self.outputs
        for port in ports:
            for pipe in port.connected_pipes:
                pipe.hide()

        super().hide()

    def show(self):
        super().show()
        ports = self.inputs + self.outputs
        for port in ports:
            for pipe in port.connected_pipes:
                pipe.show()

    def collapse(self):
        if self.collapsed or not self.hierarchical:
            return

        print("Collapse")
        for node in self._nodes:
            node.hide()

        if self._prev_size:
            self._width = self._prev_size[0]
            self._height = self._prev_size[1]
            self.post_init()
            self._prev_size = None
            self.parent.layout()

    def expand(self):
        if not self.collapsed or not self.hierarchical:
            return None

        for node in self._nodes:
            node.show()

        self.show()
        self.size_expander(self)

        [n.setSelected(True) for n in self._nodes]
        self.setSelected(True)

    def set_pos(self, x=0.0, y=0.0):
        self.pos = (x, y)
        print(self.pos)
        if not self.hierarchical:
            return

        padding = 40
        x_min = min(
            v.view.xy[1] - v.view.h / 2 for v in self.layout_vertices.values())

        y_min = min(
            v.view.xy[0] - v.view.w / 2 for v in self.layout_vertices.values())

        for n, v in self.layout_vertices.items():
            n.pos = (x + v.view.xy[1] - x_min - v.view.h / 2 + padding,
                     y + v.view.xy[0] - y_min - v.view.w / 2 + padding)

    def _add_port(self, port, display_name=True):
        port_item = PortItem(self)
        port_item.name = port.basename
        port_item.port_type = IN_PORT if isinstance(port, InPort) else OUT_PORT
        port_item.multi_connection = True
        port_item.display_name = display_name
        text = QGraphicsTextItem(port_item.name, self)
        text.font().setPointSize(8)
        text.setFont(text.font())
        text.setVisible(display_name)
        if isinstance(port, InPort):
            self._input_items[port_item] = text
        else:
            self._output_items[port_item] = text

        return port_item

    @AbstractNodeItem.selected.setter
    def selected(self, selected=False):
        AbstractNodeItem.selected.fset(self, selected)
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

    def _set_base_size(self):
        """
        setup initial base size.
        """
        width, height = self.calc_size()
        if width > self._width:
            self._width = width
        if height > self._height:
            self._height = height

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

        return width, height

    def arrange_label(self):
        """
        Arrange node label to the default top center of the node.
        """
        text_rect = self._text_item.boundingRect()
        text_x = (self._width / 2) - (text_rect.width() / 2)
        self._text_item.setPos(text_x, 1.0)

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
        if self.inputs:
            port_width = self.inputs[0].boundingRect().width()
            port_height = self.inputs[0].boundingRect().height()
            chunk = (height / len(self.inputs))
            port_x = (port_width / 2) * -1
            port_y = (chunk / 2) - (port_height / 2)
            for port in self.inputs:
                port.setPos(port_x + padding_x, port_y + (padding_y / 2))
                port_y += chunk
        # adjust input text position
        for port, text in self._input_items.items():
            txt_height = text.boundingRect().height() - 8.0
            txt_x = port.x() + port.boundingRect().width()
            txt_y = port.y() - (txt_height / 2)
            text.setPos(txt_x + 3.0, txt_y)
        # adjust output position
        if self.outputs:
            port_width = self.outputs[0].boundingRect().width()
            port_height = self.outputs[0].boundingRect().height()
            chunk = height / len(self.outputs)
            port_x = width - (port_width / 2)
            port_y = (chunk / 2) - (port_height / 2)
            for port in self.outputs:
                port.setPos(port_x, port_y + (padding_y / 2))
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

        # setup initial base size.
        self._set_base_size()
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
        self.offset_ports(0.0, 15.0)

    def add_node(self, node):
        node.update()
        node.parent = self

        self._nodes.append(node)
        v = Vertex(node)
        self.layout_vertices[node] = v

    def connect(self, port1, port2):
        node1 = port1.node
        node2 = port2.node

        port1.connect_to(port2)

        if (node2 is not self) and (node1 is not self):
            self.layout_edges.append(
                Edge(self.layout_vertices[node1], self.layout_vertices[node2]))

    def layout(self):
        if not self.hierarchical:
            return

        class defaultview:
            def __init__(self, w, h):
                self.w = h
                self.h = w

        g = Graph(list(self.layout_vertices.values()), self.layout_edges)

        for node, v in self.layout_vertices.items():
            if hasattr(node, 'layout'):
                node.layout()
            v.view = defaultview(node.width, node.height)

        sug = SugiyamaLayout(g.C[0])
        sug.init_all(roots=self.layout_root_vertices)
        sug.xspace = 20
        sug.yspace = 50

        sug.draw()

        for n, v in self.layout_vertices.items():
            n.set_pos(v.view.xy[1] - v.view.h / 2, v.view.xy[0] - v.view.w / 2)
