#!/usr/bin/python
import argparse
import os
import sys
import runpy

from PySide2 import QtGui, QtWidgets

from gearbox.graph import graph
from gearbox.gtkwave import gtkwave
from gearbox.main_window import MainWindow
from gearbox.sniper import sniper
from gearbox.which_key import which_key
from pygears.conf import Inject, MayInject, inject, reg
from pygears.conf.custom_settings import load_rc
from pygears.sim.extens.vcd import SimVCDPlugin

from . import (
    actions, buffer_actions, description_actions, file_actions, graph_actions,
    gtkwave_actions, toggle_actions, window_actions)
from .compilation import compilation
from .pygears_proxy import sim_bridge
# import gearbox.graph
from .theme import themify
from .saver import get_save_file_path, load
from .timekeep import timekeep

# @inject
# def main(layers=Inject('gearbox/layers')):
#     app = QtWidgets.QApplication(sys.argv)

#     app.setWindowIcon(QtGui.QIcon('gearbox.png'))
#     app.setFont(QtGui.QFont("DejaVu Sans Mono", 11))

#     timekeep = TimeKeep()

#     main_window = MainWindow()

#     import os
#     import __main__
#     main_window.setWindowTitle(
#         f'Gearbox - {os.path.abspath(__main__.__file__)}')

#     for l in layers:
#         l()

#     main_window.show()
#     app.exec_()


@inject
def reloader(outdir=MayInject('results-dir'), plugin=Inject('sim/gearbox')):
    if plugin.reload:
        try:
            runpy.run_path(get_save_file_path())
        except Exception as e:
            print(f'Loading save file failed: {e}')


def pygears_proc(script_fn):
    pass


@inject
def set_main_win_title(
    script_fn=Inject('gearbox/model_script_name'), main=Inject('gearbox/main/inst')):

    main.setWindowTitle(f'Gearbox - {script_fn}')


class Application(QtWidgets.QApplication):
    def quit(self):
        # import faulthandler
        # faulthandler.dump_traceback_later(1, file=open('err.log', 'w'))
        print('Quit called')
        super().quit()


@inject
def main_loop(script_fn, argv, layers=Inject('gearbox/layers')):
    import faulthandler
    faulthandler.enable(file=open('err.log', 'w'))

    reg['gearbox/main/new_model_script_fn'] = None
    # bind('gearbox/main/argv', sys_args)

    sys_args = argv.copy()
    load_rc('.gearbox', os.getcwd())

    # app = QtWidgets.QApplication(sys.argv)
    app = Application(sys_args)
    with open(os.path.join(os.path.dirname(__file__), 'default.css')) as f:
        stylesheet = f.read()

    app.setStyleSheet(themify(stylesheet))

    app.setWindowIcon(QtGui.QIcon('gearbox.png'))
    app.setFont(QtGui.QFont("DejaVu Sans Mono", 10))

    main_window = MainWindow()
    main_window.setWindowTitle(f'Gearbox')

    sim_bridge_inst = sim_bridge()
    sim_bridge_inst.script_loading_started.connect(set_main_win_title)
    sim_bridge_inst.script_loading_started.connect(load)

    for l in layers:
        l()

    if script_fn:
        load_rc('.pygears', os.path.dirname(script_fn))
        sim_bridge_inst.invoke_method('run_model', script_fn=script_fn)

    main_window.show()
    ret = app.exec_()
    script_fn = reg['gearbox/main/new_model_script_fn']
    if script_fn:
        print('Quitting: ', sys_args)
        print(('gearbox', sys_args[0], script_fn))
        cmd = [sys_args[0], 'gearbox']
        for i in range(2, len(sys_args)):
            if sys_args[i] in ['-d', '--outdir']:
                cmd.append(sys_args[i])
                cmd.append(sys_args[i + 1])

        cmd.append(script_fn)
        os.execl(*cmd)
    else:
        sys.exit(ret)


@inject
def main(argv=sys.argv, layers=Inject('gearbox/layers')):
    print(f"Started: {argv}")
    parser = argparse.ArgumentParser(prog="Gearbox - GUI for the PyGears framework")

    parser.add_argument('script', help="PyGears script", default=None, nargs='?')

    parser.add_argument(
        '-d', '--outdir', metavar='outdir', default=None, help="Output directory")

    args = parser.parse_args(argv[1:])

    reg['results-dir'] = args.outdir

    main_loop(args.script, argv)


class SimPlugin(SimVCDPlugin):
    @classmethod
    def bind(cls):
        reg['gearbox/layers'] = [timekeep, which_key, graph, gtkwave, sniper, compilation]
        reg['sim_extens/vcd/shmidcat'] = True
        reg['sim_extens/vcd/vcd_fifo'] = True
