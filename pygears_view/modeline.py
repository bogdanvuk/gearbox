from PySide2 import QtWidgets
from .stylesheet import STYLE_MODELINE
from pygears.conf import registry, Inject, reg_inject, MayInject, inject_async
from .html_utils import tabulate, fontify


class Modeline(QtWidgets.QLabel):
    @reg_inject
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setStyleSheet(STYLE_MODELINE)
        inject_async(self.sim_bridge_connect)

    def sim_bridge_connect(self, sim_bridge=Inject('viewer/sim_bridge')):
        sim_bridge.sim_refresh.connect(self.update)

    @reg_inject
    def remove(self, sim_bridge=Inject('viewer/sim_bridge')):
        sim_bridge.sim_refresh.disconnect(self.update)
        self.setParent(None)
        self.deleteLater()

    def __del__(self):
        print("Deleting the modeline")

    def update(self):
        if self.window.buff is not None:
            name = self.window.buff.name
        else:
            name = 'empty'

        timestep = registry("sim/timestep")
        if timestep is None:
            timestep = '-'

        win_id = self.window.win_id
        if self.window.active:
            win_num = fontify(f'{win_id}:', color='"darkorchid"', bold=True)
        else:
            win_num = f'{win_id}:'

        table = [[
            ('style="padding-right: 10px;"', win_num),
            ('style="padding-right: 20px;"',
             fontify(name, color='"darkorchid"', bold=True)),
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
