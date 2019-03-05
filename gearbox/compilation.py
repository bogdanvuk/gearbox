import time
import re
from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, reg_inject, bind, MayInject, registry, safe_bind
from .layout import Buffer, LayoutPlugin, show_buffer
from .html_utils import fontify
from .description import describe_file
from .theme import themify


class TailProc(QtCore.QObject):
    file_text_append = QtCore.Signal(str)

    @reg_inject
    def __init__(self,
                 compilation_log_fn,
                 sim_bridge=Inject('gearbox/sim_bridge')):
        super().__init__()

        self.compilation_log_fn = compilation_log_fn
        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)

        self.timer = QtCore.QTimer()
        self.timer.moveToThread(self.thrd)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.read)
        self.timer.setSingleShot(True)

        self.f = open(self.compilation_log_fn)
        self.thrd.started.connect(self.timer.start)
        sim_bridge.script_closed.connect(self.quit)

        self.thrd.start()

    def quit(self):
        self.timer.stop()
        self.f.close()
        self.thrd.quit()

    def read(self):
        line = self.f.readline()
        while line:
            self.file_text_append.emit(line[:-1])
            line = self.f.readline()

        self.timer.start()


class Compilation(QtWidgets.QTextBrowser):
    resized = QtCore.Signal()
    re_err_file_line = re.compile(r'(\s+)File "([^"]+)", line (\d+), in (\S+)')
    re_err_issue_line = re.compile(r'(\s+)(\S+): \[(\d+)\], (.*)')

    def __init__(self, compilation_log_fn):
        super().__init__()
        self.document().setDefaultStyleSheet(
            QtWidgets.QApplication.instance().styleSheet())
        self.tail_proc = TailProc(compilation_log_fn)
        self.tail_proc.file_text_append.connect(self.append)
        self.setLineWrapMode(QtWidgets.QTextBrowser.NoWrap)
        self.compilation_log_fn = compilation_log_fn
        self.setOpenExternalLinks(False)

    def append(self, text):
        res = self.re_err_file_line.fullmatch(text)
        if res:
            indent = res.group(1)
            fn = res.group(2)
            line = int(res.group(3))
            fn = themify(f'<a href="file:{fn}#{line}" class="err">{fn}</a>')
            func_name = res.group(4).replace('<', '&lt;').replace('>', '&gt;')
            func = f'<span class="nf">{func_name}</span>'
            text = f'<pre style="margin: 0">{indent}<span>File "{fn}", line {line}, in {func}</span></pre>'
        else:
            # import pdb; pdb.set_trace()
            res = self.re_err_issue_line.fullmatch(text)
            if res:
                indent = res.group(1)
                err_name = res.group(2)
                issue_id = int(res.group(3))
                err_text = res.group(4)
                err_ref = themify(
                    f'<a href="err:{err_name}#{issue_id}" class="nl err">{err_name}: [{issue_id}]</a>'
                )

                text = f'<pre style="margin: 0">{indent}<span>{err_ref}, {err_text}</span></pre>'

        super().append(text)

    @reg_inject
    def setSource(self, url, sim_bridge=Inject('gearbox/sim_bridge')):
        if url.scheme() == 'file':
            lineno = int(url.fragment())
            describe_file(url.path(), lineno=slice(lineno, lineno + 1))
        elif url.scheme() == 'err':
            issue_id = int(url.fragment())
            sim_bridge.invoke_method('set_err_model', issue_id=issue_id)


@reg_inject
def compilation(sim_bridge=Inject('gearbox/sim_bridge')):
    sim_bridge.script_loading_started.connect(compilation_create)


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
