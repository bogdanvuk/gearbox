#!/usr/bin/python
import inspect
from PySide2.QtCore import Qt
from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, reg_inject, registry, inject_async, bind
from .layout import active_buffer
from functools import wraps
from .main_window import Shortcut, register_prefix
import os


class Interactive:
    def __init__(self, message=None, completer=lambda: None):
        self.message = message
        self.completer = completer


class MinibufferWaiter(QtCore.QEventLoop):
    @reg_inject
    def wait(self,
             message=None,
             completer=None,
             minibuffer=Inject('gearbox/minibuffer')):
        minibuffer.complete(message, completer)
        minibuffer.completed.connect(self.completed)
        self.exec_()
        return self.resp

    def completed(self, text):
        self.resp = text
        self.quit()


def get_minibuffer_input(message=None, completer=None, text=None):
    return MinibufferWaiter().wait(message, completer)


def shortcut(domain, shortcut):
    def wrapper(func):
        sig = inspect.signature(func)
        # default values in func definition
        interactives = {
            k: v.default
            for k, v in sig.parameters.items()
            if isinstance(v.default, Interactive)
        }

        if interactives:

            @wraps(func)
            def arg_func():
                kwds = {
                    k: get_minibuffer_input(v.message, v.completer())
                    for k, v in interactives.items()
                }
                func(**kwds)

            registry('gearbox/shortcuts').append((domain, shortcut, arg_func))
        else:
            registry('gearbox/shortcuts').append((domain, shortcut, func))

    return wrapper


@shortcut(None, Qt.CTRL + Qt.Key_H)
@reg_inject
def toggle_help(which_key=Inject('gearbox/which_key')):
    if which_key.isVisible():
        which_key.hide()
    else:
        which_key.show()


@shortcut(None, Qt.Key_S)
@reg_inject
def step_simulator(sim_bridge=Inject('gearbox/sim_bridge')):
    sim_bridge.breakpoints.add(lambda: (True, False))
    if not sim_bridge.running:
        sim_bridge.cont()


class ShortcutRepeat(QtCore.QObject):
    def __init__(self, main):
        super().__init__()
        self.last_shortcut = None
        main.shortcut_triggered.connect(self.shortcut_triggered)
        self.repeat_shortcut = Shortcut(
            domain=None, key=Qt.Key_Period, callback=self.repeat)

    def repeat(self):
        if self.last_shortcut:
            self.last_shortcut.activated.emit()

    def shortcut_triggered(self, shortcut):
        if shortcut is not self.repeat_shortcut:
            self.last_shortcut = shortcut


@inject_async
def create_shortcut_repeater(main=Inject('gearbox/main')):
    bind('gearbox/shortcut_repeater', ShortcutRepeat(main))


@shortcut(None, Qt.Key_Colon)
@reg_inject
def time_search(
        time=Interactive('Time: '), timekeep=Inject('gearbox/timekeep')):

    try:
        time = int(time)
    except TypeError:
        return

    timekeep.timestep = time


register_prefix(None, Qt.Key_Space, 'SPC')
