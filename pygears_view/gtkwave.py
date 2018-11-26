from PySide2 import QtWidgets, QtGui, QtCore
import subprocess
import pexpect
import re
import os
import sys

from pygears.conf import Inject, reg_inject, registry


class GtkWaveProc(QtCore.QObject):

    window_up = QtCore.Signal(str, int, int)
    response = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gtkwave_thread = QtCore.QThread()
        self.moveToThread(self.gtkwave_thread)
        self.exiting = False
        self.gtkwave_thread.started.connect(self.run)
        self.gtkwave_thread.finished.connect(self.quit)
        self.gtkwave_thread.start()

    def run(self):
        self.p = pexpect.spawnu('gtkwave -W -N')
        self.p.expect('%')
        version = re.search(r"GTKWave Analyzer v(\d{1}\.\d{1}.\d{2})",
                            self.p.before).group(0)
        print(f"GtkWave {version} window")

        out = subprocess.check_output(
            'xwininfo -name "GTKWave - [no file loaded]"', shell=True)

        win_id = re.search(r"Window id: 0x([0-9a-fA-F]+)",
                           out.decode()).group(1)

        self.window_up.emit(version, self.p.pid, int(win_id, 16))

    def command(self, cmd, mutex=None):
        print(f'Pexpect: {cmd}')
        print(f'Pexpect thread: {self.thread()}')
        self.p.send(cmd + '\n')
        self.p.expect('%')
        print(f'Response: {self.p.before}')
        self.response.emit(self.p.before)
        if mutex:
            mutex.unlock()

    def quit(self):
        self.p.close()
        super().quit()


class GtkWaveCmdBlock(QtCore.QEventLoop):
    def command(self, cmd, gtk_wave):
        gtk_wave.send_command.emit(cmd)
        gtk_wave.proc.response.connect(self.response)
        self.exec_()
        return self.resp

    def response(self, resp):
        self.resp = resp
        self.quit()


class GtkWave(QtCore.QObject):
    send_command = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = GtkWaveProc()
        self.proc.window_up.connect(self.window_up)
        self.send_command.connect(self.proc.command)
        # self.proc.setTerminationEnabled(True)
        # self.proc.start()
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.proc.quit)
        self.cmd = None
        self.cond = QtCore.QWaitCondition()

    def closeEvent(self, event):
        # print('close event')
        self.proc.quit()

    def reclick(self):
        # print(f"Sending: xdotool {self.cmd}")
        # os.system(f"xdotool getactivewindow {self.cmd}")
        os.system(f"xdotool {self.cmd}")
        QtCore.QTimer.singleShot(10, self.reload)

    def reload(self):
        self.cmd = None
        # print("Reverting input block")
        self.gtkwave_win.setFlag(QtCore.Qt.WindowTransparentForInput, True)

    def send_input(self, cmd):
        self.cmd = cmd
        self.gtkwave_win.setFlag(QtCore.Qt.WindowTransparentForInput, False)

        if self.cmd.startswith('click'):
            QtCore.QTimer.singleShot(200, self.reclick)
        else:
            QtCore.QTimer.singleShot(10, self.reclick)

    def eventFilter(self, obj, event):
        # print(f"Gtkwave: {event.type()}")
        if not self.cmd:
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() < 200:
                    key = QtGui.QKeySequence(
                        event.key() + int(event.modifiers())).toString()
                    self.send_input(
                        f"key --window {self.win_id} {key.lower()}")
                    return True
            elif event.type() == QtCore.QEvent.MouseButtonPress:
                self.send_input(f'click --window {self.win_id} 1')
                return True

        return super().eventFilter(obj, event)

    def command_nb(self, cmd):
        self.send_command.emit(cmd)

    def command(self, cmd):
        cmd_block = GtkWaveCmdBlock()
        resp = cmd_block.command(cmd, self)
        return resp

    @reg_inject
    def window_up(self,
                  version,
                  pid,
                  win_id,
                  graph=Inject('graph/graph'),
                  outdir=Inject('sim/artifact_dir')):
        # print(f'GtkWave started: {version}, {pid}, {win_id}')
        self.win_id = win_id
        self.gtkwave_win = QtGui.QWindow.fromWinId(win_id)
        self.gtkwave_win.setFlag(QtCore.Qt.WindowTransparentForInput, True)
        self.gtkwave_widget = QtWidgets.QWidget.createWindowContainer(
            self.gtkwave_win)

        graph.buffers['gtkwave'] = self.gtkwave_widget
        self.gtkwave_widget.installEventFilter(self)

        print(f'Gtkwave thread: {self.thread()}')
        pyvcd = os.path.abspath(os.path.join(outdir, 'pygears.vcd'))
        print(f"Sending cmd: gtkwave::loadFile {pyvcd}")
        # self.send_command.emit(f'gtkwave::loadFile {pyvcd}')
        self.command(f'gtkwave::loadFile {pyvcd}')
