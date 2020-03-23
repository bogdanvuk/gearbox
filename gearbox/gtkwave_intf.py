import os
import re

import pexpect
from PySide2 import QtCore, QtGui, QtWidgets

from pygears.conf import Inject, inject, reg


class GtkEventProc(QtCore.QObject):
    def gtk_event(self, name, data):
        getattr(self, name, lambda x: x)(data)

    @inject
    def SetMarker(self, data, timekeep=Inject('gearbox/timekeep')):
        print(f'SetMarker: {data}')

        if int(data) != 0xffffffffffffffff:
            timekeep.timestep = (int(data) // 10)

    def detect_key(self, data):
        native_modifiers, native_key = map(int, data.split(','))
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

        if ((native_modifiers & 0x1) and (key > 127 or chr(key).isalpha())):
            modifiers += QtCore.Qt.SHIFT

        if native_modifiers & 0x8:
            modifiers += QtCore.Qt.ALT

        return (key, QtCore.Qt.KeyboardModifiers(modifiers), text)

    def KeyPress(self, data):

        app = QtWidgets.QApplication.instance()

        key = self.detect_key(data)

        # app.postEvent(app.focusWidget(),
        #               QtGui.QKeyEvent(QtGui.QKeyEvent.ShortcutOverride, *key))

        # app.processEvents(QtCore.QEventLoop.AllEvents)

        if app.focusWidget():
            app.postEvent(
                app.focusWidget(), QtGui.QKeyEvent(QtGui.QKeyEvent.KeyPress, *key))

    def KeyRelease(self, data):

        app = QtWidgets.QApplication.instance()

        key = self.detect_key(data)

        if app.focusWidget():
            app.postEvent(
                app.focusWidget(), QtGui.QKeyEvent(QtGui.QKeyEvent.KeyRelease, *key))


class GtkWaveProc(QtCore.QObject):

    window_up = QtCore.Signal(str, int, int)
    response = QtCore.Signal(str, int)
    gtk_event = QtCore.Signal(str, str)

    def __init__(self, trace_fn):
        super().__init__()

        self.gtkwave_thread = QtCore.QThread()
        self.trace_fn = trace_fn
        self.moveToThread(self.gtkwave_thread)
        self.exiting = False
        self.cmd_id = None
        self.shmidcat = (os.path.splitext(self.trace_fn)[-1] != '.vcd')
        self.gtkwave_thread.started.connect(self.run)
        self.gtkwave_thread.start()

    def run(self):
        # self.shmid_proc = subprocess.Popen(
        #     f'tail -f -n +1 {self.trace_fn} | shmidcat',
        #     shell=True,
        #     stdout=subprocess.PIPE)

        # vcd_shr_obj = self.shmid_proc.stdout.readline().decode().strip()

        local_dir = os.path.abspath(os.path.dirname(__file__))
        script_fn = os.path.join(local_dir, "gtkwave.tcl")
        gtkwaverc_fn = os.path.join(local_dir, "gtkwaverc")

        if self.shmidcat:
            print(f'Shared mem addr: {self.trace_fn}')
            cmd = f'gtkwave -W -I -r {gtkwaverc_fn} -T {script_fn} {self.trace_fn}'

        else:
            print(f'VCD file: {self.trace_fn}')
            cmd = f'gtkwave -W -r {gtkwaverc_fn} -T {script_fn} {self.trace_fn}'

        print(cmd)
        self.p = pexpect.spawnu(cmd)
        self.p.setecho(False)
        try:
            self.p.expect('%', timeout=4)
        except pexpect.TIMEOUT:
            print(f'Gtkwave start failed {self.trace_fn}: {self.p.before}')
            raise Exception(f'Gtkwave failed to start: {self.p.before}')

        version = re.search(r"GTKWave Analyzer v(\d{1}\.\d{1}.\d{2})", self.p.before)

        if version is None:
            raise Exception(f'Gtkwave failed to start: {self.p.before}')

        version = version.group(0)

        print(f"GtkWave {version} window")

        print(self.p.send('gtkwave::getGtkWindowID\n'))
        self.p.expect('%')
        window_id = self.p.before

        print(f'Window id: {window_id} -> {int(window_id)}')
        self.window_up.emit(version, self.p.pid, int(window_id))

        # while (self.event_proc is not None):
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
                if self.exiting:
                    self.gtkwave_thread.quit()
                    return

            # if data.strip():
            #     print(f'Unsollicited: {data}')

            for d in data.strip().split('\n'):
                res = re.search(r"^\$\$(\w+):(.*)$", d)

                if res:
                    self.gtk_event.emit(res.group(1), res.group(2))
                    self.gtkwave_thread.eventDispatcher().processEvents(
                        QtCore.QEventLoop.AllEvents)

    def command(self, cmd, cmd_id):
        self.cmd_id = cmd_id
        # print(f'GtkWave> {cmd_id}, {cmd}')
        self.p.send(cmd + '\n')
        try:
            self.p.expect('%', timeout=None)
        except pexpect.TIMEOUT:
            print("timeout")
            print(self.p.buffer)
            return

        resp = '\n'.join(
            [d for d in self.p.before.strip().split('\n') if not d.startswith("$$")])

        # print(f'GtkWave: {self.p.before.strip()}')
        # print(f'Response: {cmd_id}, {resp}')
        self.response.emit(resp, cmd_id)
        self.cmd_id = None

    def close(self):
        print("aboutToQuit gtkwave")
        self.exiting = True
        # self.gtkwave_thread.wait()


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
    0xffe1: QtCore.Qt.Key_Shift,
    0xffe2: QtCore.Qt.Key_Shift,
    0xffe3: QtCore.Qt.Key_Control,
    0xffe9: QtCore.Qt.Key_Alt,
    0xffea: QtCore.Qt.Key_Alt
}


class GtkWaveWindow(QtCore.QObject):
    send_command = QtCore.Signal(str, int)
    initialized = QtCore.Signal()
    deleted = QtCore.Signal()

    def __init__(self, trace_fn, parent=None):
        super().__init__(parent)
        self.event_proc = GtkEventProc()
        self.proc = GtkWaveProc(trace_fn)
        self.window_id = None
        # self.proc = GtkWaveProc(trace_fn, None)

        self.proc.gtk_event.connect(self.event_proc.gtk_event)
        self.proc.window_up.connect(self.window_up)
        self.send_command.connect(self.proc.command)
        self.response = self.proc.response

        self.deleted.connect(self.proc.close)
        # QtWidgets.QApplication.instance().aboutToQuit.connect(self.proc.close)

    @property
    def shmidcat(self):
        return self.proc.shmidcat

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

    @inject
    def window_up(self, version, pid, window_id, graph=Inject('gearbox/graph')):
        print(f'GtkWave started: {version}, {pid}, {window_id}')
        self.window_id = window_id
        self.gtkwave_win = QtGui.QWindow.fromWinId(window_id)
        self.widget = QtWidgets.QWidget.createWindowContainer(self.gtkwave_win)
        # self.widget.setFocusPolicy(QtCore.Qt.NoFocus)
        self.widget.setWindowFlag(QtCore.Qt.X11BypassWindowManagerHint)
        self.widget.setWindowFlag(QtCore.Qt.BypassGraphicsProxyWidget)
        self.widget.setWindowFlag(QtCore.Qt.BypassWindowManagerHint)

        self.command(f'gtkwave::toggleStripGUI')
        if reg['gearbox/gtkwave/menus']:
            self.command(f'gtkwave::toggleStripGUI')

        self.command(f'gtkwave::setZoomFactor -7')

        self.initialized.emit()

    def close(self):
        self.deleted.emit()
        self.proc.gtkwave_thread.wait()
