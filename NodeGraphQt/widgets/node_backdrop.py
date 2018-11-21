#!/usr/bin/python
from PySide2 import QtGui, QtCore
from PySide2.QtWidgets import QGraphicsItem

from NodeGraphQt.widgets.constants import (Z_VAL_PIPE, NODE_SEL_COLOR,
                                           NODE_SEL_BORDER_COLOR)
from NodeGraphQt.widgets.node_abstract import AbstractNodeItem
from NodeGraphQt.widgets.pipe import Pipe
from NodeGraphQt.widgets.port import PortItem

from NodeGraphQt.base.commands import NodeAddedCmd

from NodeGraphQt.widgets.constants import (
    IN_PORT, OUT_PORT, NODE_ICON_SIZE, ICON_NODE_BASE, NODE_SEL_COLOR,
    NODE_SEL_BORDER_COLOR, Z_VAL_NODE, Z_VAL_NODE_WIDGET)

from PySide2.QtWidgets import (QGraphicsItem, QGraphicsPixmapItem,
                               QGraphicsTextItem)

from grandalf.layouts import SugiyamaLayout
from grandalf.graphs import Vertex, Edge, Graph


class BackdropSizer(QGraphicsItem):
    def __init__(self, parent=None, size=6.0):
        super(BackdropSizer, self).__init__(parent)
        self.setFlag(self.ItemIsSelectable, True)
        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemSendsScenePositionChanges, True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.SizeFDiagCursor))
        self.setToolTip('double-click auto resize')
        self._size = size

    @property
    def size(self):
        return self._size

    def set_pos(self, x, y):
        x -= self._size
        y -= self._size
        self.setPos(x, y)

    def boundingRect(self):
        return QtCore.QRectF(0.5, 0.5, self._size, self._size)

    def itemChange(self, change, value):
        if change == self.ItemPositionChange:
            item = self.parentItem()
            mx, my = item.minimum_size
            x = mx if value.x() < mx else value.x()
            y = my if value.y() < my else value.y()
            value = QtCore.QPointF(x, y)
            item.on_sizer_pos_changed(value)
            return value
        return super(BackdropSizer, self).itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        item = self.parentItem()
        item.on_sizer_double_clicked()

    def paint(self, painter, option, widget):
        painter.save()

        rect = self.boundingRect()
        item = self.parentItem()
        if item and item.selected:
            color = QtGui.QColor(*NODE_SEL_BORDER_COLOR)
        else:
            color = QtGui.QColor(*item.color)
            color = color.darker(110)
        path = QtGui.QPainterPath()
        path.moveTo(rect.topRight())
        path.lineTo(rect.bottomRight())
        path.lineTo(rect.bottomLeft())
        painter.setBrush(color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.fillPath(path, painter.brush())

        painter.restore()


class BackdropNodeItem(AbstractNodeItem):
    """
    Base Backdrop item.
    """

    def __init__(self, name='backdrop', text='', parent=None):
        self._input_items = {}
        self._output_items = {}
        super(BackdropNodeItem, self).__init__(name, parent)
        self.setZValue(Z_VAL_PIPE - 1)
        self._properties['backdrop_text'] = text
        self._min_size = 80, 80
        self._sizer = BackdropSizer(self, 20.0)
        self._sizer.set_pos(*self._min_size)
        self._nodes = []
        self.layout_vertices = {}
        self.layout_root_vertices = []
        self.layout_edges = []
        self._prev_size = None

    def _combined_rect(self, nodes):
        group = self.scene().createItemGroup(nodes)
        rect = group.boundingRect()
        self.scene().destroyItemGroup(group)
        return rect

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            rect = QtCore.QRectF(pos.x() - 5, pos.y() - 5, 10, 10)
            item = self.scene().items(rect)[0]

            if isinstance(item, (PortItem, Pipe)):
                self.setFlag(self.ItemIsMovable, False)
                return
            if self.selected:
                return

            # viewer = self.viewer()
            # [n.setSelected(False) for n in viewer.selected_nodes()]

            # self._nodes += self.get_nodes(False)
            [n.setSelected(True) for n in self._nodes]

    def mouseReleaseEvent(self, event):
        super(BackdropNodeItem, self).mouseReleaseEvent(event)
        self.setFlag(self.ItemIsMovable, True)
        [n.setSelected(True) for n in self.get_nodes()]
        # self._nodes = [self]

    def on_sizer_pos_changed(self, pos):
        self._width = pos.x() + self._sizer.size
        self._height = pos.y() + self._sizer.size
        self.post_init()

    def mouseDoubleClickEvent(self, event):
        self.auto_resize()

    def on_sizer_double_clicked(self):
        self.auto_resize()

    def paint(self, painter, option, widget):
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

        txt_rect = QtCore.QRectF(top_rect.x(),
                                 top_rect.y() + 1.5, rect.width(),
                                 top_rect.height())
        painter.setPen(QtGui.QColor(*self.text_color))
        painter.drawText(txt_rect, QtCore.Qt.AlignCenter, self.name)

        path = QtGui.QPainterPath()
        path.addRect(rect)
        border_color = self.color
        if self.selected and NODE_SEL_BORDER_COLOR:
            border_color = NODE_SEL_BORDER_COLOR
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor(*border_color), 1))
        painter.drawPath(path)

        # import pdb; pdb.set_trace()
        for port in self.inputs + self.outputs:
            for pipe in port.connected_pipes:
                pipe.draw_path(pipe._input_port, pipe._output_port)

        painter.restore()

    def connect(self, port1, port2):
        node1 = port1.model.node.view
        node2 = port2.model.node.view

        print(f'Connecting: {port1.model.node} -> {port2.model.node}')

        port1.connect_to(port2)

        print(f'{port1.view._pipes}')

        if (node2 is not self) and (node1 is not self):
            self.layout_edges.append(
                Edge(self.layout_vertices[node1], self.layout_vertices[node2]))
        # elif node1 is self:
        #     self.layout_root_vertices.append(node2)
        # elif node2 is self:
        #     self.layout_root_vertices.append(node1)

    def add_node(self, node):
        view = node.view
        view.update()
        view.parent = self

        self._nodes.append(view)
        v = Vertex(view)
        self.layout_vertices[view] = v

        node.graph._undo_stack.push(NodeAddedCmd(node.graph, node))

    def layout(self):
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

    def get_nodes(self, inc_intersects=False):
        return [self] + self._nodes

    def hide(self):
        self.collapse()
        self.hide()

    def show(self):
        ports = self.inputs + self.outputs
        for port in ports:
            for pipe in port.connected_pipes:
                pipe.show()

        super().show()

    def collapse(self):
        for node in self._nodes:
            node.hide()

        if self._prev_size:
            self._sizer.set_pos(self._prev_size[0], self._prev_size[1])
            self._prev_size = None
            self.parent.layout()

    def expand(self):
        for node in self._nodes:
            node.show()

        self.show()

        padding = 40
        self._prev_size = (self.width, self.height)

        nodes_rect = self._combined_rect(self._nodes)

        self._sizer.set_pos(nodes_rect.width() + (padding * 2),
                            nodes_rect.height() + (padding * 2))
        self.parent.layout()

        [n.setSelected(True) for n in self.get_nodes()]

    def set_pos(self, x=0.0, y=0.0):
        self.pos = (x, y)
        print(self.pos)

        padding = 40
        x_min = min(
            v.view.xy[1] - v.view.h / 2 for v in self.layout_vertices.values())

        y_min = min(
            v.view.xy[0] - v.view.w / 2 for v in self.layout_vertices.values())

        for n, v in self.layout_vertices.items():
            n.pos = (x + v.view.xy[1] - x_min - v.view.h / 2 + padding,
                     y + v.view.xy[0] - y_min - v.view.w / 2 + padding)

    def auto_resize(self, nodes=None):
        if self._prev_size:
            self.collapse()
        else:
            self.expand()

        print(f'Size: {self.width}, {self.height}')

    def pre_init(self, viewer, pos=None):
        """
        Called before node has been added into the scene.

        Args:
            viewer (NodeGraphQt.widgets.viewer.NodeViewer): main viewer.
            pos (tuple): cursor pos.
        """
        nodes = viewer.selected_nodes()
        if nodes:
            padding = 40
            scene = viewer.scene()
            group = scene.createItemGroup(nodes)
            rect = group.boundingRect()
            scene.destroyItemGroup(group)
            self.pos = [rect.x() - padding, rect.y() - padding]
            self._sizer.set_pos(rect.width() + (padding * 2),
                                rect.height() + (padding * 2))
        else:
            self.pos = pos

    def post_init(self, viewer=None, pos=None):
        self.arrange_ports(padding_y=35.0)
        self.offset_ports(0.0, 15.0)

    @property
    def minimum_size(self):
        return self._min_size

    @minimum_size.setter
    def minimum_size(self, size=(50, 50)):
        self._min_size = size

    @property
    def backdrop_text(self):
        return self._properties['backdrop_text']

    @backdrop_text.setter
    def backdrop_text(self, text):
        self._properties['backdrop_text'] = text

    @AbstractNodeItem.width.setter
    def width(self, width=0.0):
        AbstractNodeItem.width.fset(self, width)
        self._sizer.set_pos(self._width, self._height)

    @AbstractNodeItem.height.setter
    def height(self, height=0.0):
        AbstractNodeItem.height.fset(self, height)
        self._sizer.set_pos(self._width, self._height)

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

    def add_input(self, name='input', multi_port=False, display_name=True):
        """
        Args:
            name (str): name for the port.
            multi_port (bool): allow multiple connections.
            display_name (bool): display the port name. 

        Returns:
            PortItem: input item widget
        """
        port = PortItem(self)
        port.name = name
        port.port_type = IN_PORT
        port.multi_connection = multi_port
        port.display_name = display_name
        text = QGraphicsTextItem(port.name, self)
        text.font().setPointSize(8)
        text.setFont(text.font())
        text.setVisible(display_name)
        self._input_items[port] = text
        if self.scene():
            self.post_init()
        return port

    def add_output(self, name='output', multi_port=False, display_name=True):
        """
        Args:
            name (str): name for the port.
            multi_port (bool): allow multiple connections.
            display_name (bool): display the port name. 

        Returns:
            PortItem: output item widget
        """
        port = PortItem(self)
        port.name = name
        port.port_type = OUT_PORT
        port.multi_connection = multi_port
        port.display_name = display_name
        text = QGraphicsTextItem(port.name, self)
        text.font().setPointSize(8)
        text.setFont(text.font())
        text.setVisible(display_name)
        self._output_items[port] = text
        if self.scene():
            self.post_init()
        return port

    @property
    def inputs(self):
        return list(self._input_items.keys())

    @property
    def outputs(self):
        return list(self._output_items.keys())

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
