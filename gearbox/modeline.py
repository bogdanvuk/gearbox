from PySide2 import QtWidgets
from .stylesheet import STYLE_MODELINE
from pygears.conf import reg_inject
from .html_utils import tabulate, fontify
from .theme import themify


class Modeline(QtWidgets.QLabel):
    @reg_inject
    def __init__(self, window):
        super().__init__()
        self.setAccessibleName('modeline')
        self.window = window
        self.window.buffer_changed.connect(self.update)
        self.window.activated.connect(self.update)
        self.window.deactivated.connect(self.update)
        # self.setStyleSheet(themify(STYLE_MODELINE))
        self.reset()

    def reset(self):
        self.field_order = {0: 'win_num', 1: 'name'}

        self.field_styles = {
            'win_num': 'style="padding-right: 5px;"',
            'name': 'style="padding-right: 20px;"'
        }

        self.field_text = {}

    def set_field_text(self, name, text):
        self.field_text[name] = text
        self.update()

    def add_field(self, name, style):
        self.field_styles[name] = style

    def remove(self):
        self.setParent(None)
        self.deleteLater()

    def __del__(self):
        print("Deleting the modeline")

    def update(self):
        if self.window.buff is not None:
            name = self.window.buff.name
        else:
            name = 'empty'

        win_id = self.window.win_id
        if self.window.active:
            win_num = fontify(
                f'{win_id}:',
                background_color='#d4a649',
                color='darkorchid',
                bold=True)
        else:
            win_num = f'{win_id}:'

        self.field_text['win_num'] = win_num
        self.field_text['name'] = fontify(name, color='darkorchid', bold=True)

        tbl = tabulate([[(style, self.field_text.get(name, ''))
                         for name, style in self.field_styles.items()]])

        style = """
<style>
td {
padding-left: 10px;
padding-right: 10px;
}
</style>
        """

        self.setText(style + tbl)
