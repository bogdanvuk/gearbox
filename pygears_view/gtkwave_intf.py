import subprocess
import pexpect
import re
import os

from pygears.conf import Inject, MayInject, bind, reg_inject
from PySide2 import QtWidgets, QtGui, QtCore


class GtkWaveProc(QtCore.QObject):

    window_up = QtCore.Signal(str, int, int)
    response = QtCore.Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gtkwave_thread = QtCore.QThread()
        self.moveToThread(self.gtkwave_thread)
        self.exiting = False
        self.gtkwave_thread.started.connect(self.run)
        self.gtkwave_thread.finished.connect(self.quit)
        self.gtkwave_thread.start()

    def run(self):
        local_dir = os.path.abspath(os.path.dirname(__file__))
        script_fn = os.path.join(local_dir, "gtkwave.tcl")
        self.p = pexpect.spawnu(f'gtkwave -W -N -T {script_fn}')
        self.p.setecho(False)
        self.p.expect('%')
        version = re.search(r"GTKWave Analyzer v(\d{1}\.\d{1}.\d{2})",
                            self.p.before).group(0)
        print(f"GtkWave {version} window")

        out = subprocess.check_output(
            'xwininfo -name "GTKWave - [no file loaded]"', shell=True)

        window_id = re.search(r"Window id: 0x([0-9a-fA-F]+)",
                              out.decode()).group(1)

        self.window_up.emit(version, self.p.pid, int(window_id, 16))

    def command(self, cmd, cmd_id):
        self.p.send(cmd + '\n')
        self.p.expect('%')
        self.response.emit(self.p.before, cmd_id)

    def quit(self):
        self.p.close()
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


class GtkWaveXevProc(QtCore.QObject):

    key_press = QtCore.Signal(int, int)

    def __init__(self, window_id, parent=None):
        super().__init__(parent)
        self.window_id = window_id
        self.xev_thread = QtCore.QThread()
        self.moveToThread(self.xev_thread)
        self.xev_thread.started.connect(self.run)
        self.xev_thread.start()

    def run(self):
        # cmd = ['xev', '-id', str(self.window_id), '-event', 'keyboard']
        cmd = f'xev -id {self.window_id} -event keyboard'
        # print(f"Running xev with: {' '.join(cmd)}")
        # print(f"Running xev with: {cmd}")
        import subprocess
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        key_press = False
        for line in proc.stdout:
            line = line.decode()
            # print(line, end='')
            if line.startswith("KeyPress"):
                key_press = True
            elif key_press and line.strip().startswith("state"):
                # print(line)

                res = re.search(
                    r"state 0x([0-9a-fA-F]+).*keysym 0x([0-9a-fA-F]+).*",
                    line.strip())
                # print(res)
                # print(res.group(1), res.group(2))
                native_modifiers, native_key = int(res.group(1), 16), int(
                    res.group(2), 16)

                modifiers = 0
                key = native_key
                if chr(key).islower():
                    key = ord(chr(key).upper())

                if native_modifiers & 0x4:
                    modifiers += QtCore.Qt.CTRL

                if native_modifiers & 0x1:
                    modifiers += QtCore.Qt.SHIFT

                if native_modifiers & 0x8:
                    modifiers += QtCore.Qt.ALT

                self.key_press.emit(key, modifiers)
                key_press = False

    def quit(self):
        self.xev_thread.quit()


class GtkWave(QtCore.QObject):
    send_command = QtCore.Signal(str, int)
    initialized = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = GtkWaveProc()
        self.proc.window_up.connect(self.window_up)
        self.send_command.connect(self.proc.command)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.proc.quit)

    def command_nb(self, cmd):
        self.send_command.emit(cmd, 0)

    def command(self, cmd):
        cmd_block = GtkWaveCmdBlock()
        resp = cmd_block.command(cmd, self)
        return resp

    @reg_inject
    def key_press(self, key, modifiers, graph=Inject('viewer/graph')):
        print(modifiers, key)
        app = QtWidgets.QApplication.instance()
        app.postEvent(
            graph, QtGui.QKeyEvent(QtGui.QKeyEvent.KeyPress, key, modifiers))

    @reg_inject
    def window_up(self, version, pid, window_id, graph=Inject('viewer/graph')):
        print(f'GtkWave started: {version}, {pid}, {window_id}')
        self.window_id = window_id
        self.gtkwave_win = QtGui.QWindow.fromWinId(window_id)
        self.gtkwave_widget = QtWidgets.QWidget.createWindowContainer(
            self.gtkwave_win)

        self.xev_proc = GtkWaveXevProc(window_id)
        QtWidgets.QApplication.instance().aboutToQuit.connect(
            self.xev_proc.quit)
        self.xev_proc.key_press.connect(self.key_press)

        self.initialized.emit()
