import subprocess
import pexpect
import re
import os

from pygears.conf import Inject, MayInject, bind, reg_inject
from PySide2 import QtWidgets, QtGui, QtCore


class GtkWaveProc(QtCore.QObject):

    key_press = QtCore.Signal(int, int, str)
    window_up = QtCore.Signal(str, int, int)
    response = QtCore.Signal(str, int)

    def __init__(self, trace_fn, parent=None):
        super().__init__(parent)
        self.gtkwave_thread = QtCore.QThread()
        self.trace_fn = trace_fn
        self.moveToThread(self.gtkwave_thread)
        self.exiting = False
        self.cmd_id = None
        self.gtkwave_thread.started.connect(self.run)
        self.gtkwave_thread.finished.connect(self.quit)
        self.gtkwave_thread.start()

    def run(self):
        # self.shmid_proc = subprocess.Popen(
        #     f'tail -f -n +1 {self.trace_fn} | shmidcat',
        #     shell=True,
        #     stdout=subprocess.PIPE)

        # vcd_shr_obj = self.shmid_proc.stdout.readline().decode().strip()
        print(f'Shared mem addr: {self.trace_fn}')

        local_dir = os.path.abspath(os.path.dirname(__file__))
        script_fn = os.path.join(local_dir, "gtkwave.tcl")
        gtkwaverc_fn = os.path.join(local_dir, "gtkwaverc")

        print(f'gtkwave -W -I -T {script_fn} {self.trace_fn}')
        self.p = pexpect.spawnu(
            f'gtkwave -W -I -r {gtkwaverc_fn} -T {script_fn} {self.trace_fn}')
        self.p.setecho(False)
        self.p.expect('%')
        version = re.search(r"GTKWave Analyzer v(\d{1}\.\d{1}.\d{2})",
                            self.p.before).group(0)
        print(f"GtkWave {version} window")

        # out = subprocess.check_output(
        #     'xwininfo -name "GTKWave - [no file loaded]"', shell=True)
        window_id = subprocess.check_output(
            'xdotool getactivewindow', shell=True)

        print(f'Window id: {window_id} -> {int(window_id)}')

        # window_id = re.search(r"Window id: 0x([0-9a-fA-F]+)",
        #                       out.decode()).group(1)

        # self.window_up.emit(version, self.p.pid, int(window_id, 16))
        self.window_up.emit(version, self.p.pid, int(window_id))

        while (1):
            self.gtkwave_thread.eventDispatcher().processEvents(
                QtCore.QEventLoop.AllEvents)

            # if self.cmd_id is not None:
            #     continue

            try:
                data = ''
                while True:
                    data += self.p.read_nonblocking(size=4096, timeout=0.01)
            except pexpect.TIMEOUT:
                pass

            for d in data.strip().split('\n'):
                # print(f'Unsollicited: {data}')
                res = re.search(r"KeyPress:(\d+),(\d+)", d)

                if not res:
                    continue

                native_modifiers, native_key = int(res.group(1)), int(
                    res.group(2))

                modifiers = 0
                text = ''
                key = native_key

                if key < 127:
                    text = chr(key)

                    if chr(key).islower():
                        key = ord(chr(key).upper())

                key = native_key_map.get(key, key)

                if native_modifiers & 0x4:
                    modifiers += QtCore.Qt.CTRL

                if ((native_modifiers & 0x1)
                        and (key > 127 or chr(key).isalpha())):
                    modifiers += QtCore.Qt.SHIFT

                if native_modifiers & 0x8:
                    modifiers += QtCore.Qt.ALT

                self.key_press.emit(key, modifiers, text)

                self.gtkwave_thread.eventDispatcher().processEvents(
                    QtCore.QEventLoop.AllEvents)

    def command(self, cmd, cmd_id):
        self.cmd_id = cmd_id
        self.p.send(cmd + '\n')
        try:
            # print(f'GtkWave: {cmd}')
            self.p.expect('%')
        except pexpect.TIMEOUT:
            print("timeout")
            print(self.p.buffer)
            return

        resp = '\n'.join([
            d for d in self.p.before.strip().split('\n')
            if not d.startswith("KeyPress")
        ])

        # print(f'GtkWave: {self.p.before.strip()}')
        self.response.emit(resp, cmd_id)
        self.cmd_id = None

    def quit(self):
        self.p.close()
        # self.shmid_proc.terminate()
        self.gtkwave_thread.quit()


class GtkWaveCmdBlock(QtCore.QEventLoop):
    @property
    def cmd_id(self):
        return id(self) & 0xffff

    def command(self, cmd, gtk_wave):
        self.cmd = cmd
        gtk_wave.send_command.emit(cmd, self.cmd_id)
        gtk_wave.proc.response.connect(self.response)
        self.exec_()
        return self.resp

    def response(self, resp, cmd_id):
        if cmd_id == self.cmd_id:
            self.resp = resp
            self.quit()


native_key_map = {
    0xff08: QtCore.Qt.Key_Backspace,
    0xff09: QtCore.Qt.Key_Tab,
    0xff0b: QtCore.Qt.Key_Clear,
    0xff0d: QtCore.Qt.Key_Return,
    0xff13: QtCore.Qt.Key_Pause,
    0xff14: QtCore.Qt.Key_ScrollLock,
    0xff15: QtCore.Qt.Key_SysReq,
    0xff1b: QtCore.Qt.Key_Escape,
    0xffff: QtCore.Qt.Key_Delete,
    0xff50: QtCore.Qt.Key_Home,
    0xff51: QtCore.Qt.Key_Left,
    0xff52: QtCore.Qt.Key_Up,
    0xff53: QtCore.Qt.Key_Right,
    0xff54: QtCore.Qt.Key_Down,
    0xff55: QtCore.Qt.Key_PageUp,
    0xff56: QtCore.Qt.Key_PageDown,
    0xff57: QtCore.Qt.Key_End,
}


class GtkWaveWindow(QtCore.QObject):
    send_command = QtCore.Signal(str, int)
    initialized = QtCore.Signal()

    def __init__(self, trace_fn, parent=None):
        super().__init__(parent)
        self.proc = GtkWaveProc(trace_fn)
        self.proc.key_press.connect(self.key_press)
        self.proc.window_up.connect(self.window_up)
        self.send_command.connect(self.proc.command)
        self.response = self.proc.response

        QtWidgets.QApplication.instance().aboutToQuit.connect(self.proc.quit)

    @property
    def domain(self):
        return 'gtkwave'

    def command_nb(self, cmd, cmd_id=0):
        self.send_command.emit(cmd, cmd_id)

    def command(self, cmd):
        if isinstance(cmd, list):
            cmd = 'if {1} {\n' + '\n'.join(cmd) + '\n}'

        cmd_block = GtkWaveCmdBlock()
        # from traceback import walk_stack, print_stack
        # stack_len = len(list(walk_stack(f=None)))
        # print(f'Stack len: {len(list(walk_stack(f=None)))}')
        # if stack_len > 10:
        #     print_stack()

        resp = cmd_block.command(cmd, self)
        return resp

    @reg_inject
    # def key_press(self, key, modifiers, graph=Inject('viewer/graph')):
    def key_press(self, key, modifiers, text, main=Inject('viewer/main')):
        app = QtWidgets.QApplication.instance()
        # app.postEvent(
        #     graph, QtGui.QKeyEvent(QtGui.QKeyEvent.KeyPress, key, modifiers))
        # print(f'key: {(key, modifiers, text)} -> {app.focusWidget()}')
        app.postEvent(
            app.focusWidget(),
            QtGui.QKeyEvent(QtGui.QKeyEvent.ShortcutOverride, key, modifiers,
                            text))

        # print(f'key: {(key, modifiers, text)} -> {app.focusWidget()}')
        app.processEvents(QtCore.QEventLoop.AllEvents)

        app.postEvent(
            app.focusWidget(),
            QtGui.QKeyEvent(QtGui.QKeyEvent.KeyPress, key, modifiers, text))

        app.processEvents(QtCore.QEventLoop.AllEvents)

        # app.postEvent(
        #     graph, QtGui.QKeyEvent(QtGui.QKeyEvent.KeyRelease, key, modifiers))
        app.postEvent(
            # main.centralWidget(),
            app.focusWidget(),
            QtGui.QKeyEvent(QtGui.QKeyEvent.KeyRelease, key, modifiers, text))

        app.processEvents(QtCore.QEventLoop.AllEvents)

    @reg_inject
    def window_up(self, version, pid, window_id, graph=Inject('viewer/graph')):
        print(f'GtkWave started: {version}, {pid}, {window_id}')
        self.window_id = window_id
        self.gtkwave_win = QtGui.QWindow.fromWinId(window_id)
        self.widget = QtWidgets.QWidget.createWindowContainer(self.gtkwave_win)
        # self.widget.setFocusPolicy(QtCore.Qt.NoFocus)
        self.widget.setWindowFlag(QtCore.Qt.X11BypassWindowManagerHint)
        self.widget.setWindowFlag(QtCore.Qt.BypassGraphicsProxyWidget)
        self.widget.setWindowFlag(QtCore.Qt.BypassWindowManagerHint)

        self.initialized.emit()
