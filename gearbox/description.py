from PySide2 import QtWidgets, QtGui, QtCore
from .layout import Buffer
from pygears.conf import Inject, reg_inject, bind, MayInject, registry
import pygments
from pygments.lexers import get_lexer_for_filename
from pygments.formatters import HtmlFormatter
from .stylesheet import STYLE_TEXTBROWSER
from .theme import themify

dark_theme = """
/* Dracula Theme v1.2.5
 *
 * https://github.com/zenorocha/dracula-theme
 *
 * Copyright 2016, All rights reserved
 *
 * Code licensed under the MIT license
 * http://zenorocha.mit-license.org
 *
 * @author Rob G <wowmotty@gmail.com>
 * @author Chris Bracco <chris@cbracco.me>
 * @author Zeno Rocha <hi@zenorocha.com>
 */

 .highlight .hll { background-color: rgba(150, 150, 150, 50) }
 .highlight .c { color: #6272a4 } /* Comment */
 .highlight .err { color: #f8f8f2 } /* Error */
 .highlight .g { color: #f8f8f2 } /* Generic */
 .highlight .k { color: #ff79c6 } /* Keyword */
 .highlight .l { color: #f8f8f2 } /* Literal */
 .highlight .n { color: #f8f8f2 } /* Name */
 .highlight .o { color: #ff79c6 } /* Operator */
 .highlight .x { color: #f8f8f2 } /* Other */
 .highlight .p { color: #f8f8f2 } /* Punctuation */
 .highlight .ch { color: #6272a4 } /* Comment.Hashbang */
 .highlight .cm { color: #6272a4 } /* Comment.Multiline */
 .highlight .cp { color: #ff79c6 } /* Comment.Preproc */
 .highlight .cpf { color: #6272a4 } /* Comment.PreprocFile */
 .highlight .c1 { color: #6272a4 } /* Comment.Single */
 .highlight .cs { color: #6272a4 } /* Comment.Special */
 .highlight .gd { color: #8b080b } /* Generic.Deleted */
 .highlight .ge { color: #f8f8f2; text-decoration: underline } /* Generic.Emph */
 .highlight .gr { color: #f8f8f2 } /* Generic.Error */
 .highlight .gh { color: #f8f8f2; font-weight: bold } /* Generic.Heading */
 .highlight .gi { color: #f8f8f2; font-weight: bold } /* Generic.Inserted */
 .highlight .go { color: #44475a } /* Generic.Output */
 .highlight .gp { color: #f8f8f2 } /* Generic.Prompt */
 .highlight .gs { color: #f8f8f2 } /* Generic.Strong */
 .highlight .gu { color: #f8f8f2; font-weight: bold } /* Generic.Subheading */
 .highlight .gt { color: #f8f8f2 } /* Generic.Traceback */
 .highlight .kc { color: #ff79c6 } /* Keyword.Constant */
 .highlight .kd { color: #8be9fd; font-style: italic } /* Keyword.Declaration */
 .highlight .kn { color: #ff79c6 } /* Keyword.Namespace */
 .highlight .kp { color: #ff79c6 } /* Keyword.Pseudo */
 .highlight .kr { color: #ff79c6 } /* Keyword.Reserved */
 .highlight .kt { color: #8be9fd } /* Keyword.Type */
 .highlight .ld { color: #f8f8f2 } /* Literal.Date */
 .highlight .m { color: #bd93f9 } /* Literal.Number */
 .highlight .s { color: #f1fa8c } /* Literal.String */
 .highlight .na { color: #50fa7b } /* Name.Attribute */
 .highlight .nb { color: #8be9fd; font-style: italic } /* Name.Builtin */
 .highlight .nc { color: #50fa7b } /* Name.Class */
 .highlight .no { color: #f8f8f2 } /* Name.Constant */
 .highlight .nd { color: #f8f8f2 } /* Name.Decorator */
 .highlight .ni { color: #f8f8f2 } /* Name.Entity */
 .highlight .ne { color: #f8f8f2 } /* Name.Exception */
 .highlight .nf { color: #50fa7b } /* Name.Function */
 .highlight .nl { color: #8be9fd; font-style: italic } /* Name.Label */
 .highlight .nn { color: #f8f8f2 } /* Name.Namespace */
 .highlight .nx { color: #f8f8f2 } /* Name.Other */
 .highlight .py { color: #f8f8f2 } /* Name.Property */
 .highlight .nt { color: #ff79c6 } /* Name.Tag */
 .highlight .nv { color: #8be9fd; font-style: italic } /* Name.Variable */
 .highlight .ow { color: #ff79c6 } /* Operator.Word */
 .highlight .w { color: #f8f8f2 } /* Text.Whitespace */
 .highlight .mb { color: #bd93f9 } /* Literal.Number.Bin */
 .highlight .mf { color: #bd93f9 } /* Literal.Number.Float */
 .highlight .mh { color: #bd93f9 } /* Literal.Number.Hex */
 .highlight .mi { color: #bd93f9 } /* Literal.Number.Integer */
 .highlight .mo { color: #bd93f9 } /* Literal.Number.Oct */
 .highlight .sa { color: #f1fa8c } /* Literal.String.Affix */
 .highlight .sb { color: #f1fa8c } /* Literal.String.Backtick */
 .highlight .sc { color: #f1fa8c } /* Literal.String.Char */
 .highlight .dl { color: #f1fa8c } /* Literal.String.Delimiter */
 .highlight .sd { color: #f1fa8c } /* Literal.String.Doc */
 .highlight .s2 { color: #f1fa8c } /* Literal.String.Double */
 .highlight .se { color: #f1fa8c } /* Literal.String.Escape */
 .highlight .sh { color: #f1fa8c } /* Literal.String.Heredoc */
 .highlight .si { color: #f1fa8c } /* Literal.String.Interpol */
 .highlight .sx { color: #f1fa8c } /* Literal.String.Other */
 .highlight .sr { color: #f1fa8c } /* Literal.String.Regex */
 .highlight .s1 { color: #f1fa8c } /* Literal.String.Single */
 .highlight .ss { color: #f1fa8c } /* Literal.String.Symbol */
 .highlight .bp { color: #f8f8f2; font-style: italic } /* Name.Builtin.Pseudo */
 .highlight .fm { color: #50fa7b } /* Name.Function.Magic */
 .highlight .vc { color: #8be9fd; font-style: italic } /* Name.Variable.Class */
 .highlight .vg { color: #8be9fd; font-style: italic } /* Name.Variable.Global */
 .highlight .vi { color: #8be9fd; font-style: italic } /* Name.Variable.Instance */
 .highlight .vm { color: #8be9fd; font-style: italic } /* Name.Variable.Magic */
 .highlight .il { color: #bd93f9 } /* Literal.Number.Integer.Long */
"""

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
        # self.setStyleSheet(themify(STYLE_TEXTBROWSER))
        self.document().setDefaultStyleSheet(QtWidgets.QApplication.instance().styleSheet())
        self.clean()

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

        self.setHtml(
            pygments.highlight(contents, get_lexer_for_filename(fn),
                               HtmlFormatter(hl_lines=hl_lines)))
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
