from PySide2 import QtWidgets
from .stylesheet import STYLE_MODELINE
from pygears.conf import registry, Inject, reg_inject, MayInject, inject_async
from .html_utils import tabulate, fontify
from .timekeep import timestep_event_register


class Modeline(QtWidgets.QLabel):
    @reg_inject
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setStyleSheet(STYLE_MODELINE)
        timestep_event_register(self.update)

    @reg_inject
    def remove(self, timekeep=Inject('viewer/timekeep')):
        timekeep.timestep_changed.disconnect(self.update)
        self.setParent(None)
        self.deleteLater()

    def __del__(self):
        print("Deleting the modeline")

    @reg_inject
    def update(self, timestep=Inject('viewer/timestep')):
        if self.window.buff is not None:
            name = self.window.buff.name
        else:
            name = 'empty'

        if timestep is None:
            timestep = '-'

        win_id = self.window.win_id
        if self.window.active:
            win_num = fontify(
                f'{win_id}:',
                background_color='#d4a649',
                color='darkorchid',
                bold=True)
        else:
            win_num = f'{win_id}:'

        table = [[
            ('style="padding-right: 5px;"', win_num),
            ('style="padding-right: 20px;"',
             fontify(name, color='darkorchid', bold=True)),
            ('', f'Timestep: {timestep}'),
        ]]
        tbl = tabulate(table)

        style = """
<style>
td {
padding-left: 10px;
padding-right: 10px;
}
</style>
        """

        self.setText(style + tbl)
