#!/usr/bin/python
import inspect
from PySide2.QtCore import Qt
from PySide2 import QtCore
from pygears.conf import Inject, reg, inject, inject_async
from functools import wraps
from .main_window import Shortcut, register_prefix


class Interactive:
    def __init__(self, message=None, completer=lambda: None):
        self.message = message
        self.completer = completer


class MinibufferWaiter(QtCore.QEventLoop):
    @inject
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


def shortcut(domain, shortcut, name=None):
    def wrapper(func):
        sig = inspect.signature(func)
        # default values in func definition
        interactives = {
            k: v.default
            for k, v in sig.parameters.items()
            if isinstance(v.default, Interactive)
        }

        if name is None:
            sh_name = func.__name__
        else:
            sh_name = name

        if interactives:

            @wraps(func)
            def arg_func():
                kwds = {
                    k: get_minibuffer_input(v.message, v.completer())
                    for k, v in interactives.items()
                }
                func(**kwds)

            reg['gearbox/shortcuts'].append((domain, shortcut, arg_func,
                                                  sh_name))
        else:
            reg['gearbox/shortcuts'].append((domain, shortcut, func,
                                                  sh_name))

    return wrapper


@shortcut(None, Qt.CTRL + Qt.Key_H)
@inject
def toggle_help(which_key=Inject('gearbox/which_key')):
    if which_key.isVisible():
        which_key.hide()
    else:
        which_key.show()


class ShortcutRepeat(QtCore.QObject):
    def __init__(self, main):
        super().__init__()
        self.last_shortcut = None
        main.shortcut_triggered.connect(self.shortcut_triggered)
        self.repeat_shortcut = Shortcut(
            domain=None,
            key=Qt.Key_Period,
            callback=self.repeat,
            name='repeat command')

    def repeat(self):
        if self.last_shortcut:
            self.last_shortcut.activated.emit()

    def shortcut_triggered(self, shortcut):
        if shortcut is not self.repeat_shortcut:
            self.last_shortcut = shortcut


@inject_async
def create_shortcut_repeater(main=Inject('gearbox/main/inst')):
    reg['gearbox/shortcut_repeater'] = ShortcutRepeat(main)


register_prefix(None, Qt.Key_Space, 'SPC')
