import os
from functools import partial
from PySide2.QtCore import Qt
from PySide2 import QtWidgets
from pygears.conf import Inject, reg_inject, registry
from .utils import single_shot_connect
from .main_window import register_prefix
from .actions import shortcut
from .saver import save

register_prefix(None, (Qt.Key_Space, Qt.Key_F), 'file')


def open_file(script_fn, sim_bridge=Inject('gearbox/sim_bridge')):
    print("Invoke run_model")
    registry('gearbox/sim_bridge').invoke_method(
        'run_model', script_fn=script_fn)

    registry('gearbox/sim_bridge').invoke_method('run_sim')


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.Key_F), 'open')
@reg_inject
def open_file_interact():
    ret = QtWidgets.QFileDialog.getOpenFileName(
        caption='Open file',
        dir=os.getcwd(),
        filter="PyGears script (*.py);;All files (*)")

    script_fn = ret[0]

    if script_fn:
        open_file(script_fn)


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.Key_C), 'close')
@reg_inject
def close_file(
        sim_bridge=Inject('gearbox/sim_bridge'),
        layout=Inject('gearbox/layout')):
    sim_bridge.invoke_method('close_model')
    layout.clear_layout()


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.SHIFT + Qt.Key_C),
          'close & save layout')
@reg_inject
def close_file_save_layout(
        sim_bridge=Inject('gearbox/sim_bridge'),
        layout=Inject('gearbox/layout')):
    save()
    sim_bridge.invoke_method('close_model')
    layout.clear_layout()


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.Key_R), 'reload')
@reg_inject
def reload_file(
        sim_bridge=Inject('gearbox/sim_bridge'),
        script_fn=Inject('gearbox/model_script_name'),
        layout=Inject('gearbox/layout')):

    if script_fn:
        layout.clear_layout()
        single_shot_connect(sim_bridge.model_closed,
                            partial(open_file, script_fn))
        sim_bridge.invoke_method('close_model')


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.SHIFT + Qt.Key_R),
          'reload & save layout')
@reg_inject
def reload_file_save_layout(
        sim_bridge=Inject('gearbox/sim_bridge'),
        script_fn=Inject('gearbox/model_script_name'),
        layout=Inject('gearbox/layout')):

    if script_fn:
        save()
        layout.clear_layout()
        single_shot_connect(sim_bridge.model_closed,
                            partial(open_file, script_fn))
        sim_bridge.invoke_method('close_model')
