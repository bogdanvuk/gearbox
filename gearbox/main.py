#!/usr/bin/python
import sys
import argparse

from PySide2 import QtGui, QtWidgets, QtCore

from gearbox.main_window import MainWindow
from gearbox.graph import graph
from gearbox.which_key import which_key
from gearbox.gtkwave import gtkwave
from gearbox.sniper import sniper
from gearbox.description import description
from pygears.sim.extens.vcd import SimVCDPlugin
from pygears.conf import Inject, reg_inject, safe_bind, PluginBase, registry, bind, MayInject
from .pygears_proxy import sim_bridge
from .saver import get_save_file_path
from .timekeep import timekeep
# import gearbox.graph
from .saver import load
from . import actions
from . import window_actions
from . import file_actions
from . import graph_actions
from . import buffer_actions
from . import gtkwave_actions
from . import description_actions

# @reg_inject
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


@reg_inject
def reloader(
        outdir=MayInject('sim/artifact_dir'), plugin=Inject('sim/gearbox')):
    if plugin.reload:
        try:
            runpy.run_path(get_save_file_path())
        except Exception as e:
            print(f'Loading save file failed: {e}')


def pygears_proc(script_fn):
    pass


@reg_inject
def set_main_win_title(
        script_fn=Inject('gearbox/model_script_name'),
        main=Inject('gearbox/main')):

    main.setWindowTitle(f'Gearbox - {script_fn}')


@reg_inject
def main_loop(script_fn, layers=Inject('gearbox/layers')):
    app = QtWidgets.QApplication(sys.argv)

    app.setWindowIcon(QtGui.QIcon('gearbox.png'))
    app.setFont(QtGui.QFont("DejaVu Sans Mono", 11))

    main_window = MainWindow()
    main_window.setWindowTitle(f'Gearbox')

    sim_bridge_inst = sim_bridge()
    sim_bridge_inst.model_loaded.connect(set_main_win_title)
    sim_bridge_inst.model_loaded.connect(load)

    for l in layers:
        l()

    if script_fn:
        sim_bridge_inst.invoke_method('run_model', script_fn=script_fn)
        sim_bridge_inst.invoke_method('run_sim')

    main_window.show()
    app.exec_()


@reg_inject
def main(argv=sys.argv, layers=Inject('gearbox/layers')):
    parser = argparse.ArgumentParser(
        prog="Gearbox - GUI for the PyGears framework")

    parser.add_argument(
        'script', help="PyGears script", default=None, nargs='?')

    args = parser.parse_args(argv[1:])

    main_loop(args.script)


class SimPlugin(SimVCDPlugin):
    @classmethod
    def bind(cls):
        safe_bind(
            'gearbox/layers',
            # [which_key, graph, main, sniper, description, reloader])
            [timekeep, which_key, graph, gtkwave, sniper])
        safe_bind('sim/extens/vcd/shmidcat', True)
        safe_bind('sim/extens/vcd/vcd_fifo', True)
