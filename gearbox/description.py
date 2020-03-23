from PySide2 import QtWidgets, QtGui, QtCore
from .layout import Buffer
from pygears.conf import Inject, inject, reg
import pygments
from pygments.lexers import get_lexer_for_filename, PythonLexer, Python3Lexer, ClassNotFound
from pygments.formatters import HtmlFormatter

#         self.setHtml("""
# <div class="highlight">
# <pre><span class="k">print</span> <span class="s">&quot;Hello World&quot;</span></pre>
# </div>
#         """)


class DescriptionBuffer(Buffer):
    @property
    def domain(self):
        return 'description'


@inject
def description():
    viewer = Description()
    DescriptionBuffer(viewer, 'description')
    reg['gearbox/description'] = viewer


class Description(QtWidgets.QTextEdit):
    resized = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.document().setDefaultStyleSheet(
            QtWidgets.QApplication.instance().styleSheet())
        self.clean()
        palette = self.palette()
        palette.setBrush(QtGui.QPalette.Highlight,
                         QtGui.QColor(0xd0, 0xd0, 0xff, 40))

        palette.setBrush(QtGui.QPalette.HighlightedText,
                         QtGui.QBrush(QtCore.Qt.NoBrush))

        self.setPalette(palette)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QtGui.QPainter(self.viewport())
        p.fillRect(self.cursorRect(), QtGui.QBrush(QtCore.Qt.white))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    def clean(self):
        self.fn = None
        self.lineno = None
        self.trace = None
        self.trace_pos = None

    def display_text(self, text):
        self.clean()
        self.setHtml(text)

    def display_trace(self, trace):
        self.clean()
        self.trace = trace
        self.set_trace_pos(0)

    def set_trace_pos(self, pos):
        self.trace_pos = pos
        frame, lineno = self.trace[self.trace_pos]
        self.display_file(frame.f_code.co_filename, slice(lineno, lineno + 1))

    def display_file(self, fn, lineno=1):
        with open(fn, 'r') as f:
            contents = f.read()

        self.fn = fn
        self.lineno = lineno

        if isinstance(lineno, slice):
            start = lineno.start
        else:
            start = lineno
            lineno = slice(lineno, lineno + 1)

        try:
            lexer = get_lexer_for_filename(fn)
            if isinstance(lexer, PythonLexer):
                lexer = Python3Lexer()

            html = pygments.highlight(contents, lexer, HtmlFormatter())
        except ClassNotFound:
            html = contents

        # print(html)
        self.setHtml(html)
        self.update()

        # import pdb; pdb.set_trace()
        start_text_block = self.document().findBlockByLineNumber(lineno.start -
                                                                 1)
        end_text_block = self.document().findBlockByLineNumber(lineno.stop - 1)

        c = self.textCursor()
        c.setPosition(start_text_block.position())
        c.setPosition(end_text_block.position(), QtGui.QTextCursor.KeepAnchor)
        self.moveCursor(QtGui.QTextCursor.End)
        self.setTextCursor(c)

        # cursor = QtGui.QTextCursor(
        #     self.document().findBlockByLineNumber(start - 1))

        # # cursor.movePosition(QtGui.QTextCursor.Down, QtGui.QTextCursor.KeepAnchor,
        # #                     10)

        # self.setTextCursor(cursor)


@inject
def describe_text(text, desc=Inject('gearbox/description')):
    desc.display_text(text)


@inject
def describe_file(fn, name=None, lineno=1, layout=Inject('gearbox/layout')):
    if name is None:
        name = fn

    for b in layout.buffers:
        if b.name == fn:
            buff = b
            break
    else:
        buff = DescriptionBuffer(Description(), fn)

    buff.view.display_file(fn, lineno)

    return buff


@inject
def describe_trace(trace, name, layout=Inject('gearbox/layout')):
    for b in layout.buffers:
        if b.name == name:
            buff = b
            break
    else:
        buff = DescriptionBuffer(Description(), name)

    buff.view.display_trace(trace)
    return buff
