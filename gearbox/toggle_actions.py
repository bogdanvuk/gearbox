from PySide2.QtCore import Qt
from pygears.conf import reg
from .main_window import register_prefix
from .actions import shortcut

register_prefix(None, (Qt.Key_Space, Qt.Key_T), 'toggle')


@shortcut(None, (Qt.Key_Space, Qt.Key_T, Qt.Key_M))
def toggle_menu():
    reg['gearbox/main/menus'] = not reg['gearbox/main/menus']


@shortcut(None, (Qt.Key_Space, Qt.Key_T, Qt.Key_T))
def toggle_tabbar():
    reg['gearbox/main/tabbar'] = not reg['gearbox/main/tabbar']
