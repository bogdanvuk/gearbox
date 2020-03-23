from PySide2 import QtCore, QtGui, QtWidgets

from pygears.conf import Inject, inject, reg

from .theme import ThemePlugin


class NodeScene(QtWidgets.QGraphicsScene):
    @inject
    def __init__(self,
                 parent=None,
                 background_color=Inject('gearbox/theme/background-color'),
                 grid_color=Inject('gearbox/theme/graph-grid-color')):
        super(NodeScene, self).__init__(parent)
        self.background_color = QtGui.QColor(background_color)
        self.grid_color = grid_color
        self.grid = True

    def __repr__(self):
        return '{}.{}(\'{}\')'.format(self.__module__, self.__class__.__name__,
                                      self.viewer())

    def _draw_grid(self, painter, rect, pen, grid_size):
        lines = []
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        x = left
        while x < rect.right():
            x += grid_size
            lines.append(QtCore.QLineF(x, rect.top(), x, rect.bottom()))
        y = top
        while y < rect.bottom():
            y += grid_size
            lines.append(QtCore.QLineF(rect.left(), y, rect.right(), y))
        painter.setPen(pen)
        painter.drawLines(lines)

    def drawBackground(self, painter, rect):
        painter.save()

        # bg_color = QtGui.QColor(*self._bg_color)
        bg_color = self.background_color
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        painter.setBrush(bg_color)
        painter.drawRect(rect)

        if not self.grid:
            return

        zoom = self.viewer().get_zoom()
        grid_size = 20

        if zoom > -0.5:
            pen = QtGui.QPen(QtGui.QColor(self.grid_color), 0.65)
            self._draw_grid(painter, rect, pen, grid_size)

        color = bg_color.darker(300)
        if zoom < -0.0:
            color = color.darker(100 - int(zoom * 110))
        pen = QtGui.QPen(color, 0.65)
        self._draw_grid(painter, rect, pen, grid_size * 8)

        # fix border issue on the scene edge.
        pen = QtGui.QPen(bg_color, 1)
        pen.setCosmetic(True)
        path = QtGui.QPainterPath()
        path.addRect(rect)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.restore()

    def viewer(self):
        return self.views()[0] if self.views() else None


class ScenePlugin(ThemePlugin):
    @classmethod
    def bind(cls):
        reg.confdef('gearbox/theme/graph-grid-color', default='#404040')
