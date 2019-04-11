#!/usr/bin/python
import argparse
import os
import sys

from PySide2 import QtCore
from gearbox.description import description
from PySide2 import QtCore, QtGui, QtWidgets

from gearbox.graph import graph
from gearbox.gtkwave import gtkwave
from gearbox.main_window import MainWindow
from gearbox.sniper import sniper
from gearbox.which_key import which_key
from pygears.conf import (Inject, MayInject, PluginBase, bind, reg_inject,
                          registry, safe_bind)
from pygears.conf.custom_settings import load_rc
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
        outdir=MayInject('sim/artifacts_dir'), plugin=Inject('sim/gearbox')):
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


class Application(QtWidgets.QApplication):
    def quit(self):
        # import faulthandler
        # faulthandler.dump_traceback_later(1, file=open('err.log', 'w'))
        print('Quit called')
        super().quit()


@reg_inject
def main_loop(script_fn, layers=Inject('gearbox/layers')):
    import faulthandler
    faulthandler.enable(file=open('err.log', 'w'))

    bind('gearbox/main/new_model_script_fn', None)
    sys_args = sys.argv.copy()
    # bind('gearbox/main/argv', sys_args)

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
    script_fn = registry('gearbox/main/new_model_script_fn')
    if script_fn:
        print('Quitting: ', sys_args)
        print(('gearbox', sys_args[0], script_fn))
        os.execl(sys_args[0], 'gearbox', script_fn)
    else:
        sys.exit(ret)


@reg_inject
def main(argv=sys.argv, layers=Inject('gearbox/layers')):
    print(f"Started: {sys.argv}")
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
