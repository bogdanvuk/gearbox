from PySide2 import QtWidgets, QtGui, QtCore
from .layout import Buffer
from pygears.conf import Inject, reg_inject, bind, MayInject, registry
import pygments
from pygments.lexers import get_lexer_for_filename, PythonLexer, Python3Lexer
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


@reg_inject
def description():
    viewer = Description()
    DescriptionBuffer(viewer, 'description')
    bind('gearbox/description', viewer)


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
            hl_lines = list(range(lineno.start, lineno.stop))
            start = lineno.start
        else:
            hl_lines = []
            start = lineno

        lexer = get_lexer_for_filename(fn)
        if isinstance(lexer, PythonLexer):
            lexer = Python3Lexer()

        print(lexer)

        html = pygments.highlight(contents, lexer,
                                  HtmlFormatter(hl_lines=hl_lines))
        # print(html)
        self.setHtml(html)
        self.update()

        self.moveCursor(QtGui.QTextCursor.End)
        cursor = QtGui.QTextCursor(
            self.document().findBlockByLineNumber(start - 1))

        # cursor.movePosition(QtGui.QTextCursor.Down, QtGui.QTextCursor.KeepAnchor,
        #                     10)

        self.setTextCursor(cursor)


@reg_inject
def describe_text(text, desc=Inject('gearbox/description')):
    desc.display_text(text)


@reg_inject
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


@reg_inject
def describe_trace(trace, name, layout=Inject('gearbox/layout')):
    for b in layout.buffers:
        if b.name == name:
            buff = b
            break
    else:
        buff = DescriptionBuffer(Description(), name)

    buff.view.display_trace(trace)
    return buff
