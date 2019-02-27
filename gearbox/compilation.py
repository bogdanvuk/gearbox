import time
import re
from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, reg_inject, bind, MayInject, registry, safe_bind
from .layout import Buffer, LayoutPlugin, show_buffer
from .html_utils import fontify
from .description import describe_file
from .stylesheet import STYLE_TEXTBROWSER
from .theme import themify


class TailProc(QtCore.QObject):
    file_text_append = QtCore.Signal(str)

    def __init__(self, compilation_log_fn):
        super().__init__()

        self.compilation_log_fn = compilation_log_fn
        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)
        self.thrd.started.connect(self.run)
        self.thrd.start()

    def run(self):
        with open(self.compilation_log_fn) as f:
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)  # Sleep briefly
                    continue
                self.file_text_append.emit(line[:-1])

        self.thrd.quit()


class Compilation(QtWidgets.QTextBrowser):
    resized = QtCore.Signal()
    re_err_line = re.compile(r'(\s+)File "([^"]+)", line (\d+), in (\S+)')

    def __init__(self, compilation_log_fn):
        super().__init__()
        self.tail_proc = TailProc(compilation_log_fn)
        self.tail_proc.file_text_append.connect(self.append)
        self.setLineWrapMode(QtWidgets.QTextBrowser.NoWrap)
        self.compilation_log_fn = compilation_log_fn
        self.setOpenExternalLinks(False)

    def append(self, text):
        res = self.re_err_line.fullmatch(text)
        if res:
            indent = res.group(1)
            fn = res.group(2)
            line = res.group(3)
            fn = f'<a href="{fn}#{line}" style="color:#d07070">{fn}</a>'
            func = fontify(
                res.group(4).replace('<', '&lt;').replace('>', '&gt;'),
                color='darkorchid')
            # margin-left: {len(indent)*10}px
            text = f'<p style="margin: 0;margin-left: {len(indent)}em">File "{fn}", line {line}, in {func}</p>'

            print(text)
            super().append(text)
        else:
            super().append(text)

    def setSource(self, url):
        lineno = int(url.fragment())
        describe_file(url.path(), lineno=slice(lineno, lineno + 1))


@reg_inject
def compilation(sim_bridge=Inject('gearbox/sim_bridge')):
    sim_bridge.model_loading_started.connect(compilation_create)


class CompilationBuffer(Buffer):
    @property
    def domain(self):
        return 'compilation'


@reg_inject
def compilation_create(
        sim_bridge=Inject('gearbox/sim_bridge'),
        compilation_log_fn=Inject('gearbox/compilation_log_fn')):

    buff = CompilationBuffer(Compilation(compilation_log_fn), 'compilation')
    show_buffer(buff)
    return buff
