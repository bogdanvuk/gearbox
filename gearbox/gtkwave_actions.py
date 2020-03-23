from PySide2.QtCore import Qt
from PySide2 import QtCore
from .actions import shortcut
from .layout import active_buffer
from .gtkwave import GtkWaveBufferPlugin
from .graph import GraphBufferPlugin
from pygears.conf import Inject, inject_async, inject, MayInject, reg
from .sim_actions import time_search, step_simulator, cont_simulator
from .timestep_modeline import TimestepModeline


@inject
def node_expand_toggle(status, node, gtkwave=Inject('gearbox/gtkwave/inst')):
    if status:
        gtkwave.update_pipe_statuses(node.pipes)


@inject_async
def create_node_expand_toggle(
        graph=Inject('gearbox/graph'), gtkwave=Inject('gearbox/gtkwave/inst')):
    graph.node_expand_toggled.connect(node_expand_toggle)


@shortcut('gtkwave', (Qt.Key_T, Qt.Key_M))
def toggle_menu():
    reg['gearbox/gtkwave/menus'] = not reg['gearbox/gtkwave/menus']


@shortcut('gtkwave', Qt.Key_J)
def trace_down():
    active_buffer().intf.gtkwave_intf.command('trace_down')


@shortcut('gtkwave', Qt.Key_K)
def trace_up():
    active_buffer().intf.gtkwave_intf.command('trace_up')


@shortcut('gtkwave', Qt.Key_Return)
def trace_toggle():
    active_buffer().intf.gtkwave_intf.command('gtkwave::/Edit/Toggle_Group_Open|Close')


# @inject_async
# def graph_gtkwave_select_sync(graph=Inject('gearbox/graph')):
#     bind('gearbox/graph_gtkwave_select_sync', GraphGtkwaveSelectSync(graph))


# TODO: broken when using gtkwave save file
class GraphGtkwaveSelectSync(QtCore.QObject):
    @inject
    def __init__(self, buff):
        super().__init__()
        buff.view.selection_changed.connect(self.selection_changed)
        self.buff = buff

    @inject
    def selection_changed(self, selected,
                          gtkwave=MayInject('gearbox/gtkwave/inst')):

        if not gtkwave:
            return

        selected_wave_pipes = {}
        for s in selected:
            gtkwave_intf = gtkwave.item_gtkwave_intf(s.model)
            if gtkwave_intf:
                if gtkwave_intf not in selected_wave_pipes:
                    selected_wave_pipes[gtkwave_intf] = []
            else:
                continue

            wave_intf = gtkwave_intf.items_on_wave.get(s.model, None)
            if wave_intf:
                selected_wave_pipes[gtkwave_intf].append(wave_intf)

        for intf, wave_list in selected_wave_pipes.items():
            intf.gtkwave_intf.command([
                'gtkwave::/Edit/UnHighlight_All',
                f'gtkwave::highlightSignalsFromList {{{" ".join(wave_list)}}}'
            ])

    def delete(self):
        self.deleteLater()


shortcut('gtkwave', Qt.Key_S)(step_simulator)
shortcut('gtkwave', Qt.Key_C)(cont_simulator)
shortcut('gtkwave', Qt.Key_Colon)(time_search)


class GtkwaveActionsPlugin(GraphBufferPlugin, GtkWaveBufferPlugin):
    @classmethod
    def bind(cls):
        reg['gearbox/plugins/graph']['GraphGtkwaveSelectSync'] = GraphGtkwaveSelectSync

        reg['gearbox/plugins/gtkwave']['TimestepModeline'] = TimestepModeline
