import os
from PySide2.QtCore import Qt
from PySide2 import QtWidgets
from pygears.conf import Inject, inject, reg
from .main_window import register_prefix
from .actions import shortcut
from .saver import save

register_prefix(None, (Qt.Key_Space, Qt.Key_F), 'file')


@inject
def close_file(
        sim_bridge=Inject('gearbox/sim_bridge'),
        script_fn=Inject('gearbox/model_script_name'),
        layout=Inject('gearbox/layout')):

    if script_fn is not None:
        sim_bridge.invoke_method('close_script')
        # layout.clear()


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.Key_F), 'open')
@inject
def open_file_interact(
        sim_bridge=Inject('gearbox/sim_bridge'),
        prev_script_fn=Inject('gearbox/model_script_name'),
):
    ret = QtWidgets.QFileDialog.getOpenFileName(
        caption='Open file',
        dir=os.getcwd(),
        filter="PyGears script (*.py);;All files (*)")

    script_fn = ret[0]

    if script_fn:
        if prev_script_fn:
            reg['gearbox/main/new_model_script_fn'] = script_fn
            close_file()
        else:
            reg['gearbox/sim_bridge'].invoke_method(
                'run_model', script_fn=script_fn)


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.Key_C), 'close')
@inject
def close_file_interact():
    close_file()


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.SHIFT + Qt.Key_C),
          'close & save layout')
@inject
def close_file_save_layout(
        sim_bridge=Inject('gearbox/sim_bridge'),
        layout=Inject('gearbox/layout')):
    save()
    close_file()


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.Key_R), 'reload')
@inject
def reload_file(
        sim_bridge=Inject('gearbox/sim_bridge'),
        script_fn=Inject('gearbox/model_script_name'),
        layout=Inject('gearbox/layout')):

    if script_fn:
        reg['gearbox/main/new_model_script_fn'] = script_fn
        close_file()


@shortcut(None, (Qt.Key_Space, Qt.Key_F, Qt.SHIFT + Qt.Key_R),
          'reload & save layout')
@inject
def reload_file_save_layout(
        sim_bridge=Inject('gearbox/sim_bridge'),
        script_fn=Inject('gearbox/model_script_name'),
        layout=Inject('gearbox/layout')):

    if script_fn:
        save()
        reg['gearbox/main/new_model_script_fn'] = script_fn
        close_file()
