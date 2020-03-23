#!/usr/bin/python

from PySide2 import QtCore, QtGui, QtWidgets
from pygears.conf import inject

from .constants import (
    PIPE_DEFAULT_COLOR, PIPE_ACTIVE_COLOR, PIPE_HIGHLIGHT_COLOR,
    PIPE_STYLE_DASHED, PIPE_STYLE_DEFAULT, PIPE_STYLE_DOTTED, PIPE_WIDTH,
    IN_PORT, OUT_PORT, Z_VAL_PIPE, PIPE_WAITED_COLOR, PIPE_HANDSHAKED_COLOR)
from .theme import themify

PIPE_STYLES = {
    PIPE_STYLE_DEFAULT: QtCore.Qt.PenStyle.SolidLine,
    PIPE_STYLE_DASHED: QtCore.Qt.PenStyle.DashDotDotLine,
    PIPE_STYLE_DOTTED: QtCore.Qt.PenStyle.DotLine
}

PIPE_SIM_STATUS_COLOR = {
    'empty': '#7f9597',
    'active': '#b4325a',
    'waited': '#325aa0',
    'handshaked': '#3c6414',
    'error': '@text-color-error'
}


class Pipe(QtWidgets.QGraphicsPathItem):
    """
    Base Pipe Item.
    """

    @inject
    def __init__(self, output_port, input_port, parent, model):
        super().__init__(parent)
        self.parent = parent
        self.setZValue(Z_VAL_PIPE)
        self.setAcceptHoverEvents(True)
        self.setFlags(self.ItemIsSelectable)
        self.width = PIPE_WIDTH
        self._color = None
        self._style = PIPE_STYLE_DEFAULT
        self._active = False
        self._highlight = False
        self._input_port = input_port
        self._output_port = output_port
        self.model = model
        self.layout_path = []
        self.set_status("empty")
        # self.set_tooltip()

    def show_tooltip(self):
        tooltip = '<b>{}</b><br/>'.format(self.model.name)
        from pygears.typing.pprint import pprint
        disp = pprint.pformat(self.model.rtl.dtype, indent=4, width=30)
        tooltip += disp.replace('\n', '<br/>')
        self.setToolTip(tooltip)

    def __str__(self):
        return self.model.name

    def __repr__(self):
        return f'{type(self)}({str(self)})'

    def set_status(self, status):
        self.status = status
        new_color = themify(PIPE_SIM_STATUS_COLOR[status])
        if new_color != self.color:
            self.color = new_color
            self.update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # self.setFlag(self.ItemIsMovable, True)
        self.setSelected(True)

    def hoverEnterEvent(self, event):
        self.activate()

    def hoverLeaveEvent(self, event):
        self.reset()
        if self.isSelected():
            self.highlight()

    def paint(self, painter, option, widget):
        color = QtGui.QColor(self._color)
        pen_style = PIPE_STYLES.get(self.style)

        if self.status == 'empty':
            pen_width = PIPE_WIDTH
        else:
            pen_width = PIPE_WIDTH * 3

        if self._active:
            color = QtGui.QColor(*PIPE_HIGHLIGHT_COLOR)
        elif self.isSelected():
            color = QtGui.QColor(*PIPE_HIGHLIGHT_COLOR)
            pen_style = PIPE_STYLES.get(PIPE_STYLE_DEFAULT)

        pen = QtGui.QPen(color, pen_width)
        pen.setStyle(pen_style)
        pen.setCapStyle(QtCore.Qt.RoundCap)

        painter.setPen(pen)
        painter.setRenderHint(painter.Antialiasing, True)
        painter.drawPath(self.path())

    def spline(self, pos1, pos2, start=True):
        ctr_offset_x1, ctr_offset_x2 = pos1.x(), pos2.x()
        tangent = ctr_offset_x1 - ctr_offset_x2
        tangent = (tangent * -1) if tangent < 0 else tangent

        if start:
            ctr_offset_x1 -= tangent
        else:
            ctr_offset_x2 += tangent

        # ctr_offset_x1 -= tangent
        # ctr_offset_x2 += tangent

        ctr_point1 = QtCore.QPointF(ctr_offset_x1, pos1.y())
        ctr_point2 = QtCore.QPointF(ctr_offset_x2, pos2.y())

        return ctr_point1, ctr_point2

    def draw_path(self):
        path = QtGui.QPainterPath()

        qp_start = self.input_port.plug_pos(self.parentItem(), IN_PORT)
        qp_end = self.output_port.plug_pos(self.parentItem(), OUT_PORT)

        path.moveTo(qp_end)
        for i in range(2, len(self.layout_path), 3):
            path.cubicTo(*self.layout_path[i:i + 3])

        path.lineTo(qp_start)

        self.setPath(path)

    def activate(self):
        self._active = True
        pen = QtGui.QPen(QtGui.QColor(*PIPE_HIGHLIGHT_COLOR), 2)
        pen.setStyle(PIPE_STYLES.get(PIPE_STYLE_DEFAULT))
        self.setPen(pen)

    def active(self):
        return self._active

    def highlight(self):
        self.setSelected(True)

    def highlighted(self):
        return self.isSelected()

    def reset(self):
        self._active = False
        self._highlight = False
        pen = QtGui.QPen(QtGui.QColor(self.color), 2)
        pen.setStyle(PIPE_STYLES.get(self.style))
        self.setPen(pen)

    @property
    def input_port(self):
        return self._input_port

    @property
    def output_port(self):
        return self._output_port

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self._color = color

    @property
    def style(self):
        return self._style

    @style.setter
    def style(self, style):
        self._style = style

    def delete(self):
        if self.input_port and self.input_port.connected_pipes:
            self.input_port.remove_pipe(self)
        if self.output_port and self.output_port.connected_pipes:
            self.output_port.remove_pipe(self)
        if self.scene():
            self.scene().removeItem(self)
        # TODO: not sure if we need this...?
        del self
