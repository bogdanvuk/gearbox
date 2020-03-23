import pygraphviz as pgv
from PySide2 import QtCore, QtGui, QtWidgets

from pygears.conf import Inject, inject
from pygears.core.port import InPort

from . import gv_utils
from .constants import NODE_SEL_BORDER_COLOR, NODE_SEL_COLOR, Z_VAL_NODE
from .node_abstract import AbstractNodeItem
from .pipe import Pipe
from .port import PortItem
from .theme import themify

NODE_SIM_STATUS_COLOR = {
    'empty_hier': '#303a45',
    'empty': '#32000000',
    'stuck': '#c8aa325a',
    'stuck_hier': '#c8aa325a',
    'error': '@text-color-error',
    'error_hier': '@text-color-error'
}


def node_layout(self):
    self._width, self._height = calc_node_size(self)
    self.post_init()


def minimized_painter(self, painter, option, widget):
    painter.save()
    painter.setBrush(QtGui.QColor(*self.color))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawEllipse(5, 5, self._width, self._height)

    path = QtGui.QPainterPath()
    path.addEllipse(5, 5, self._width, self._height)
    border_color = self.border_color
    if self.selected and NODE_SEL_BORDER_COLOR:
        border_color = NODE_SEL_BORDER_COLOR
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.setPen(QtGui.QPen(QtGui.QColor(*border_color), 3))
    painter.drawPath(path)

    painter.restore()


def minimized_layout(self):
    self._width, self._height = 10, 10
    self._text_item.hide()

    for port, text in self._input_items.items():
        port.setPos(self._width, self._height)
        port.hide()
        text.hide()

    for port, text in self._output_items.items():
        port.setPos(self._width, self._height)
        port.hide()
        text.hide()


def hier_layout(self):
    if self.collapsed:
        node_layout(self)
        return

    for node in self._nodes:
        if hasattr(node, 'layout'):
            node.layout()

    for node in self._nodes:
        gvn = self.get_layout_node(node)
        try:
            del gvn.attr['width']
            del gvn.attr['height']
        except KeyError:
            pass

        if node._layout != minimized_layout:
            # gvn.attr['label'] = gv_utils.get_node_record(node).replace(
            #     '\n', '')
            node_layout_rec = gv_utils.get_node_record(node)
            # print('-' * 60)
            # print(f'Node layout for {node.model.name}')
            # print('-' * 60)
            # print(node_layout_rec)
            gvn.attr['label'] = node_layout_rec.replace('\n', '')
        else:
            gvn.attr['label'] = ""
            gvn.attr['width'] = 1 / 72
            gvn.attr['height'] = 1 / 72

    if not self.layout_graph.subgraphs():
        self.layout_graph.add_subgraph([
            self.layout_graph.get_node(f'i{i}')
            for i in range(len(self.inputs))
        ],
                                       'sources',
                                       rank='same')
        self.layout_graph.add_subgraph([
            self.layout_graph.get_node(f'o{i}')
            for i in range(len(self.outputs))
        ],
                                       'sink',
                                       rank='same')

    # for i in range(len(self.inputs)):
    #     gvn = self.layout_graph.get_node(f'i{i}')

    # for i in range(len(self.outputs)):
    #     gvn = self.layout_graph.get_node(f'o{i}')

    # for pipe in self.pipes:
    #     gve = self.get_layout_edge(pipe)

    self.layout_graph.layout(prog='dot')

    # if self.model.name == '/riscv':
    #     # if self.model.name == '':
    #     self.layout_graph.draw('proba.png')
    #     self.layout_graph.draw('proba.dot')

    # self.layout_graph.draw(f'{self.model.name.replace("/", "_")}.png')
    # self.layout_graph.draw(f'{self.model.name.replace("/", "_")}.dot')

    def gv_point_load(point):
        return tuple(float(num) for num in point.split(',')[-2:])

    # if self.name:
    #     import pdb; pdb.set_trace()

    padding_y = 40
    padding_x = -5

    bounding_box = None
    # print(f"Layout for: {node.name}")
    for node in self._nodes:
        gvn = self.get_layout_node(node)
        pos = gv_point_load(gvn.attr['pos'])
        node_bounding_box = QtCore.QRectF(pos[0] - node.width / 2,
                                          pos[1] - node.height / 2, node.width,
                                          node.height)
        # print(
        #     f'  bb: {node.name}: {pos[0], pos[1], float(gvn.attr["width"])*72, float(gvn.attr["height"])*72} -> {node_bounding_box}'
        # )
        node.setPos(node_bounding_box.x(), node_bounding_box.y())
        if bounding_box is None:
            bounding_box = node_bounding_box
        else:
            bounding_box = bounding_box.united(node_bounding_box)

    if self.inputs:
        port_height = self.inputs[0].boundingRect().height()

        for i, p in enumerate(self.inputs):
            gvn = self.layout_graph.get_node(f'i{i}')
            pos = gv_point_load(gvn.attr['pos'])
            node_bounding_box = QtCore.QRectF(pos[0] - port_height / 2,
                                              pos[1] - port_height / 2 + 0.5,
                                              port_height, port_height)
            # print(
            #     f'  bb: {p.name}: {pos[0], pos[1], float(gvn.attr["width"])*72, float(gvn.attr["height"])*72} -> {node_bounding_box}'
            # )
            p.setPos(node_bounding_box.x(), node_bounding_box.y())
            bounding_box = bounding_box.united(node_bounding_box)

    if self.outputs:
        port_height = self.outputs[0].boundingRect().height()

        for i, p in enumerate(self.outputs):
            gvn = self.layout_graph.get_node(f'o{i}')
            pos = gv_point_load(gvn.attr['pos'])
            node_bounding_box = QtCore.QRectF(pos[0] - port_height / 2,
                                              pos[1] - port_height / 2 + 0.5,
                                              port_height, port_height)
            # print(
            #     f'  bb: {p.name}: {pos[0], pos[1], float(gvn.attr["width"])*72, float(gvn.attr["height"])*72} -> {node_bounding_box}'
            # )
            p.setPos(node_bounding_box.x(), node_bounding_box.y())
            bounding_box = bounding_box.united(node_bounding_box)

    for pipe in self.pipes:
        gve = self.get_layout_edge(pipe)
        path = [gv_point_load(point) for point in gve.attr['pos'].split()]
        pipe.layout_path = [QtCore.QPointF(p[0], p[1]) for p in path]

        # max_y = max(max_y, *(p.y() for p in pipe.layout_path))

    self.layers = []

    class Layer(list):
        def __init__(self, node):
            super().__init__([node])
            self.rect = node.boundingRect()
            self.rect.translate(node.pos())

        def __str__(self):
            return str(self.rect)

        def __repr__(self):
            return repr(self.rect)

        def add(self, node):
            rect = node.boundingRect()
            rect.translate(node.pos())

            if ((self.rect.left() < rect.right())
                    and (self.rect.right() > rect.left())):
                self.append(node)
                self.sort(key=lambda n: n.y())
                return True
            else:
                return False

    def find_layer(node):
        for layer in self.layers:
            if layer.add(node):
                return
        else:
            self.layers.append(Layer(node))

    # print(f"  Bounding box: {bounding_box}")

    self.layers = sorted(self.layers, key=lambda l: l.rect.left())
    for node in self._nodes:
        find_layer(node)

    for item in (self._nodes + self.inputs + self.outputs):
        # node.setY(max_y - node.y() + padding)
        item.setPos(
            item.x() - bounding_box.x() + padding_x,
            bounding_box.height() -
            (item.y() - bounding_box.y() + item._height) + padding_y)
        # print(f'  {item.name}: {item.pos()}')

    for p in self.inputs:
        p.setX(padding_x)

    for p in self.outputs:
        p.setX(bounding_box.width() + padding_x)

    for pipe in self.pipes:
        for p in pipe.layout_path:
            p.setX(p.x() - bounding_box.x() + padding_x)
            p.setY(bounding_box.height() - (p.y() - bounding_box.y()) +
                   padding_y)

    if self.parent is not None:
        self.size_expander(self)
    else:
        for p in self.pipes:
            p.draw_path()


def calc_node_size(self):
    """
    calculate minimum node size.
    """
    title_width = self._text_item.boundingRect().width()

    port_names_width = 0.0
    port_height = 0.0
    if self._input_items:
        input_widths = []
        for port, text in self._input_items.items():
            input_width = port.boundingRect().width() * 2
            if text.isVisible():
                input_width += text.boundingRect().width()
            input_widths.append(input_width)
        port_names_width += max(input_widths)
        port = list(self._input_items.keys())[0]
        port_height = port.boundingRect().height() * 2
    if self._output_items:
        output_widths = []
        for port, text in self._output_items.items():
            output_width = port.boundingRect().width() * 2
            if text.isVisible():
                output_width += text.boundingRect().width()
            output_widths.append(output_width)
        port_names_width += max(output_widths)
        port = list(self._output_items.keys())[0]
        port_height = port.boundingRect().height() * 2

    height = port_height * (max([len(self.inputs), len(self.outputs)]) + 2)
    height += 10
    width = max(port_names_width, title_width)

    return width, height


def hier_expand(node, padding=40):
    bound = node.node_bounding_rect

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
        node._height = height + padding * 3 / 2

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
    if self.collapsed:
        painter.setBrush(QtGui.QColor(themify(self.status_color)))
    else:
        painter.setBrush(QtGui.QColor(*self.border_color))

    painter.setPen(QtCore.Qt.NoPen)
    painter.drawRect(top_rect)

    if self.selected and NODE_SEL_COLOR:
        sel_color = [x for x in NODE_SEL_COLOR]
        sel_color[-1] = 10
        painter.setBrush(QtGui.QColor(*sel_color))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRect(rect)

    path = QtGui.QPainterPath()
    path.addRect(rect)
    border_color = self.border_color
    if self.selected and NODE_SEL_BORDER_COLOR:
        border_color = NODE_SEL_BORDER_COLOR
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.setPen(QtGui.QPen(QtGui.QColor(*border_color), 1))
    painter.drawPath(path)

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
    # painter.setBrush(QtGui.QColor(0, 0, 0, 50))
    painter.setBrush(QtGui.QColor(themify(self.status_color)))
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

    painter.restore()


class NodeItem(AbstractNodeItem):
    @inject
    def __init__(self,
                 name,
                 layout,
                 parent=None,
                 model=None,
                 graph=Inject('gearbox/graph')):
        super().__init__(name)

        self._layout = layout
        self.parent = parent
        self.graph = graph
        self.model = model
        self.layout_graph = pgv.AGraph(
            directed=True, rankdir='LR', splines='true', strict=False)

        self.layout_pipe_map = {}

        self._text_item = QtWidgets.QGraphicsTextItem(self.name, self)
        self._input_items = {}
        self._output_items = {}
        self._nodes = []
        self.pipes = []
        self.minimum_size = (80, 80)

        self.layout_vertices = {}
        self.layout_root_vertices = []
        self.layout_edges = []
        self.layout_inport_vertices = {}
        self.layout_outport_vertices = {}

        self.collapsed = False if parent is None else True
        self.layers = []

    def setup_done(self):
        self._hide_single_port_labels()

        self.layout()

        # for node in self._nodes:
        #     gvn = self.get_layout_node(node)
        #     for i in range(len(self.inputs)):
        #         self.layout_graph.add_edge(
        #             self.layout_graph.get_node(f'i{i}'), gvn, style='invis')

        #     for i in range(len(self.outputs)):
        #         self.layout_graph.add_edge(
        #             gvn, self.layout_graph.get_node(f'o{i}'), style='invis')

    def mouseDoubleClickEvent(self, event):
        self.auto_resize()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # self.setFlag(self.ItemIsMovable, True)
        self.selected = True

    @property
    def hierarchical(self):
        return bool(self._nodes)

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

        if not self.collapsed:
            for obj in self.children:
                obj.show()

        ports = self.inputs + self.outputs
        for port in ports:
            for pipe in port.connected_pipes:
                if pipe.input_port.isVisible() and pipe.output_port.isVisible(
                ):
                    pipe.show()

    def collapse(self):
        if self.collapsed or not self.hierarchical:
            return

        for obj in self.children:
            obj.hide()

        self.collapsed = True
        self.size_expander(self)
        self.graph.top.layout()
        self.graph.ensureVisible(self)
        self.graph.node_expand_toggled.emit(False, self.model)

    def expand(self):
        if not self.collapsed or not self.hierarchical:
            return None

        for obj in self.children:
            obj.show()

        self.collapsed = False
        self.show()
        self.graph.top.layout()
        self.graph.ensureVisible(self)
        self.selected = True
        self.graph.node_expand_toggled.emit(True, self.model)

    def get_visible_objs(self, objtype):
        for n in self._nodes:
            if (objtype is None) or (objtype is NodeItem):
                yield n

            if not n.collapsed:
                yield from n.get_visible_objs(objtype)

        if (objtype is None) or (objtype is Pipe):
            for p in self.pipes:
                yield p

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
            port_node_name = f'i{len(self._input_items)}'
            self.layout_graph.add_node(
                port_node_name, label='', width=1 / 72, height=1 / 72)
            self._input_items[port_item] = text
        else:
            port_node_name = f'o{len(self._output_items)}'
            self.layout_graph.add_node(
                port_node_name, label='', width=1 / 72, height=1 / 72)

            self._output_items[port_item] = text

        return port_item

    def set_status(self, status):
        self.status = status
        if self.model.hierarchical:
            status = f'{status}_hier'

        new_color = NODE_SIM_STATUS_COLOR[status]
        if new_color != self.status_color:
            self.status_color = new_color
            self.update()

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
        tooltip = '<b>{}</b>'.format(self.model.name)
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

        # print(f"Port arrangement for {self.name}")
        # for p in (self.inputs + self.outputs):
        #     print(f'    {p.name}: {p.pos()}')

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
        # self._tooltip_disable(self.disabled)

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

    def add_pipe(self, pipe):
        if self.parent is not None:
            pipe.setParentItem(self)
        else:
            self.graph.scene().addItem(pipe)

        self.pipes.append(pipe)

        node1 = pipe.output_port.parentItem()
        node2 = pipe.input_port.parentItem()

        tailport = ''
        if node1._layout != minimized_layout:
            tailport = f'o{pipe.output_port.model.index}'

        headport = ''
        if node2._layout != minimized_layout:
            headport = f'i{pipe.input_port.model.index}'

        if (node2 is not self) and (node1 is not self):
            self.layout_graph.add_edge(
                id(node1),
                id(node2),
                tailport=tailport,
                headport=headport,
                key=id(pipe))

        elif (node2 is self):
            self.layout_graph.add_edge(
                id(node1),
                f'o{pipe.input_port.model.index}',
                tailport=tailport,
                key=id(pipe))
        else:
            self.layout_graph.add_edge(
                f'i{pipe.output_port.model.index}',
                id(node2),
                headport=headport,
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
            node1_id = f'i{pipe.output_port.model.index}'
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
        self._layout(self)
