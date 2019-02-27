#!/usr/bin/python
import argparse
import os
import sys

from PySide2 import QtCore, QtGui, QtWidgets

from gearbox.description import description
from gearbox.graph import graph
from gearbox.gtkwave import gtkwave
from gearbox.main_window import MainWindow
from gearbox.sniper import sniper
from gearbox.which_key import which_key
from pygears.conf import (Inject, MayInject, PluginBase, bind, reg_inject,
                          registry, safe_bind)
from pygears.conf.custom_settings import RCSettings
from pygears.sim.extens.vcd import SimVCDPlugin

from . import (actions, buffer_actions, description_actions, file_actions,
               graph_actions, gtkwave_actions, toggle_actions, window_actions)
from .compilation import compilation
from .pygears_proxy import sim_bridge
# import gearbox.graph
from .theme import themify
from .saver import get_save_file_path, load
from .timekeep import timekeep

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
        main=Inject('gearbox/main/inst')):

    main.setWindowTitle(f'Gearbox - {script_fn}')


@reg_inject
def main_loop(script_fn, layers=Inject('gearbox/layers')):
    settings = RCSettings(rc_fn='.gearbox')

    app = QtWidgets.QApplication(sys.argv)
    with open(os.path.join(os.path.dirname(__file__), 'default.css')) as f:
        stylesheet = f.read()

    app.setStyleSheet(themify(stylesheet))

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
            [timekeep, which_key, graph, gtkwave, sniper, compilation])
        safe_bind('sim/extens/vcd/shmidcat', True)
        safe_bind('sim/extens/vcd/vcd_fifo', True)
