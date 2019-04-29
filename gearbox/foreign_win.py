import subprocess
import pexpect
import re
import os
from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, MayInject, bind, inject

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


def convert_native_key(state, key):
    key = native_key_map.get(key, key)
    modifiers = 0

    text = ''

    if key < 127:
        text = chr(key)

    if state & 0x4:
        modifiers += QtCore.Qt.CTRL

    if ((state & 0x1) and (key > 127 or chr(key).isalpha())):
        modifiers += QtCore.Qt.SHIFT

    if state & 0x8:
        modifiers += QtCore.Qt.ALT

    return key, modifiers, text


class ForeignProc(QtCore.QObject):

    key_press = QtCore.Signal(int, int, str)
    window_up = QtCore.Signal(int)
    response = QtCore.Signal(str, int)

    def __init__(self, cmd, prompt=None, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self.prompt = prompt
        self.thrd = QtCore.QThread()
        self.moveToThread(self.thrd)
        self.exiting = False
        self.cmd_id = None
        self.thrd.started.connect(self.run)
        self.thrd.finished.connect(self.quit)
        self.thrd.start()

    def key_press_slot(self, key, modifiers, text):
        self.key_press.emit(key, modifiers, text)

    def run(self):
        # import os
        # print(os.environ['PATH'])
        # import pdb
        # pdb.set_trace()
        if self.prompt:
            self.p = pexpect.spawnu(self.cmd)
            self.p.setecho(False)
            self.p.expect(self.prompt)
        else:
            self.p = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, shell=True)

        window_id_pid = None

        print(f'xdotool search --maxdepth 1 --pid {self.p.pid}')

        self.thrd.msleep(1000)

        # while (not window_id_pid):
        #     try:
        #         window_id_pid = subprocess.check_output(
        #             f'xdotool search --maxdepth 1 --pid {self.p.pid}',
        #             shell=True)
        #     except subprocess.CalledProcessError as e:
        #         print(f'Xdotool failed: {e.output}')
        #         self.thrd.msleep(1000)

        # # window_id_str = window_id_pid.decode().strip().split('\n')[0]
        # # window_id = int(window_id_str)

        # self.thrd.msleep(200)
        window_act_id = subprocess.check_output(
            'xdotool getactivewindow', shell=True).decode().strip()
        print(
            f'Active window id: {int(window_act_id)}: {hex(int(window_act_id))}'
        )

        self.window_up.emit(int(window_act_id))

        # self.xev_proc = ForeignXevProc(int(window_act_id))
        # self.xev_proc.key_press.connect(self.key_press_slot)

        if self.prompt:
            while (1):
                self.thrd.eventDispatcher().processEvents(
                    QtCore.QEventLoop.AllEvents)

                if self.cmd_id is not None:
                    continue

                try:
                    data = ''
                    while True:
                        data += self.p.read_nonblocking(
                            size=4096, timeout=0.01)
                except pexpect.TIMEOUT:
                    pass

                for d in data.strip().split('\n'):
                    print(f'Unsollicited: {data}')
                    # continue

                    # self.thrd.eventDispatcher().processEvents(
                    #     QtCore.QEventLoop.AllEvents)
        else:
            for line in self.p.stdout:
                self.thrd.eventDispatcher().processEvents(
                    QtCore.QEventLoop.AllEvents)

                line = line.decode()
                print(f'Unsollicited: {line}')

    def command(self, cmd, cmd_id):
        self.cmd_id = cmd_id
        self.p.send(cmd + '\n')
        # print(f'GtkWave: {cmd}')
        self.p.expect('%')
        # print(f'GtkWave: {self.p.before.strip()}')
        self.response.emit(self.p.before.strip(), cmd_id)
        self.cmd_id = None

    def quit(self):
        self.p.close()
        self.thrd.quit()


class ForeignXevProc(QtCore.QObject):

    key_press = QtCore.Signal(int, int, str)

    def __init__(self, window_id, parent=None):
        super().__init__(parent)
        self.window_id = window_id
        self.xev_thread = QtCore.QThread()
        self.moveToThread(self.xev_thread)
        self.xev_thread.started.connect(self.run)
        self.xev_thread.start()

    def run(self):
        cmd = (f'xev -id {self.window_id} -event keyboard'
               ' | grep -A2 --line-buffered "^KeyRelease"')
        # cmd = (f'xev -id {self.window_id}')

        print(f"Running xev with: {cmd}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        for line in proc.stdout:
            line = line.decode()
            print(line, end='')
            if line.strip().startswith("state"):
                # print(line)

                res = re.search(
                    r"state 0x([0-9a-fA-F]+).*keysym 0x([0-9a-fA-F]+).*",
                    line.strip())
                key, modifiers, text = convert_native_key(
                    int(res.group(1), 16), int(res.group(2), 16))

                self.key_press.emit(key, modifiers, text)

    def quit(self):
        self.xev_thread.quit()


class ForeignWindow(QtCore.QObject):
    initialized = QtCore.Signal()

    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self.proc = ForeignProc(cmd)
        self.proc.key_press.connect(self.key_press)
        self.proc.window_up.connect(self.window_up)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.proc.quit)

    @inject
    def key_press(self, key, modifiers, text, main=Inject('gearbox/main/inst')):
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

    def eventFilter(self, obj, event):
        print(f'bla: {event.type()}')
        if event.type() == QtCore.QEvent.KeyPress:
            pass

        return QtCore.QObject.eventFilter(self, obj, event)

    @inject
    def window_up(self, window_id, graph=Inject('gearbox/graph')):
        self.window_id = window_id
        print(f'Window id: {window_id}: {hex(self.window_id)}')
        self.window = QtGui.QWindow.fromWinId(window_id)
        self.widget = QtWidgets.QWidget.createWindowContainer(self.window)

        # self.widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        # graph.clearFocus()
        self.widget.activateWindow()
        self.widget.setFocus()

        # self.widget.installEventFilter(self)
        self.widget.setWindowFlag(QtCore.Qt.X11BypassWindowManagerHint)
        self.widget.setWindowFlag(QtCore.Qt.BypassGraphicsProxyWidget)
        self.widget.setWindowFlag(QtCore.Qt.BypassWindowManagerHint)

        self.initialized.emit()
