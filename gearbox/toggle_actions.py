from PySide2.QtCore import Qt
from pygears.conf import config
from .main_window import register_prefix
from .actions import shortcut

register_prefix(None, (Qt.Key_Space, Qt.Key_T), 'toggle')


@shortcut(None, (Qt.Key_Space, Qt.Key_T, Qt.Key_M))
def toggle_menu():
    config['gearbox/main/menus'] = not config['gearbox/main/menus']


@shortcut(None, (Qt.Key_Space, Qt.Key_T, Qt.Key_T))
def toggle_tabbar():
    config['gearbox/main/tabbar'] = not config['gearbox/main/tabbar']
