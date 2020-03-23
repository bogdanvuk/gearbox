import os
import inspect
from .layout import show_buffer
from .graph import GraphBufferPlugin
from .pipe import Pipe
from .popup_desc import popup_desc, popup_cancel
from functools import wraps
from PySide2.QtCore import Qt
from pygears.conf import Inject, inject, reg
from .main_window import register_prefix, message
from .actions import shortcut, get_minibuffer_input, Interactive
from .description import describe_text, describe_trace, describe_file
from .gtkwave import ItemNotTraced
from .node_search import node_search_completer
from .sim_actions import time_search, step_simulator, cont_simulator
from .timestep_modeline import TimestepModeline


def single_select_action(func):
    @wraps(func)
    @inject
    def wrapper(graph=Inject('gearbox/graph')):
        items = graph.selected_items()
        if len(items) == 1:
            func(items[0], graph)

    return wrapper


@shortcut('graph', Qt.SHIFT + Qt.Key_K)
@single_select_action
def node_up_level(node, graph):
    if isinstance(node, Pipe) or node.collapsed:
        graph.select(node.parent)
    else:
        node.collapse()


@shortcut('graph', Qt.SHIFT + Qt.Key_J)
@single_select_action
def node_down_level(node, graph):
    if isinstance(node, Pipe):
        return

    if node.collapsed:
        node.expand()

    if node.layers:
        graph.select(node.layers[0][0])


@shortcut('graph', Qt.Key_L)
@single_select_action
def node_right(node, graph):
    if isinstance(node, Pipe):
        return

    layer_id, layer, node_id = get_node_layer(node)

    if layer_id == len(node.parent.layers) - 1:
        layer_id = 0
    else:
        layer_id += 1

    closest = node.parent.layers[layer_id][0]

    for n in node.parent.layers[layer_id][1:]:
        if abs(node.y() - n.y()) < abs(node.y() - closest.y()):
            closest = n

    graph.select(closest)


@shortcut('graph', Qt.Key_H)
@single_select_action
def node_left(node, graph):
    if isinstance(node, Pipe):
        return

    layer_id, layer, node_id = get_node_layer(node)

    if layer_id == 0:
        layer_id = len(node.parent.layers) - 1
    else:
        layer_id -= 1

    closest = node.parent.layers[layer_id][0]

    for n in node.parent.layers[layer_id][1:]:
        if abs(node.y() - n.y()) < abs(node.y() - closest.y()):
            closest = n

    graph.select(closest)


def get_node_layer(node):
    for i, layer in enumerate(node.parent.layers):
        if node in layer:
            return i, layer, layer.index(node)
    else:
        return None


register_prefix('graph', Qt.Key_Z, 'zoom')


@shortcut('graph', (Qt.Key_Z, Qt.Key_Z))
@inject
def zoom_selected(graph=Inject('gearbox/graph')):
    graph.zoom_to_nodes(graph.selected_nodes())


@shortcut('graph', (Qt.Key_Z, Qt.Key_A))
@inject
def zoom_all(graph=Inject('gearbox/graph')):
    graph.fit_all()


@shortcut('graph', Qt.Key_K)
@inject
def node_up(graph=Inject('gearbox/graph')):
    nodes = graph.selected_nodes()
    if len(nodes) > 1:
        return

    if len(nodes) == 0:
        graph.select(graph.top.layers[-1][-1])
        return

    node = nodes[0]
    layer_id, layer, node_id = get_node_layer(node)
    if node_id == 0:
        if layer_id == 0:
            layer_id = len(node.parent.layers) - 1
        else:
            layer_id -= 1

        node = node.parent.layers[layer_id][-1]
    else:
        node = node.parent.layers[layer_id][node_id - 1]

    graph.select(node)


@shortcut('graph', Qt.Key_J)
@inject
def node_down(graph=Inject('gearbox/graph')):
    nodes = graph.selected_nodes()
    if len(nodes) > 1:
        return

    if len(nodes) == 0:
        graph.select(graph.top.layers[0][0])
        return

    node = nodes[0]
    layer_id, layer, node_id = get_node_layer(node)
    if node_id == len(layer) - 1:
        if layer_id == len(node.parent.layers) - 1:
            layer_id = 0
        else:
            layer_id += 1

        node = node.parent.layers[layer_id][0]
    else:
        node = node.parent.layers[layer_id][node_id + 1]

    graph.select(node)


@shortcut('graph', Qt.Key_V)
@single_select_action
def print_description(node, graph):
    if isinstance(node, Pipe):
        intf = node.model.rtl
        print(f'Interface {intf.name}: {repr(intf.dtype)}')
    else:
        rtl_node = node.model.rtl
        print(f'Node: {rtl_node.name}')
        print('paremeters: ')
        import pprint
        pprint.pprint(rtl_node.params)


@shortcut('graph', (Qt.Key_D, Qt.Key_O))
@single_select_action
def describe_item(node, graph):
    describe_text(node.model.description)


@shortcut('graph', (Qt.Key_D, Qt.Key_I))
@single_select_action
def describe_inst(node, graph):
    if not isinstance(node, Pipe):
        buff = describe_trace(
            node.model.rtl.gear.trace, name=f'inst - {node.model.rtl.name}')
        show_buffer(buff)


@shortcut('graph', (Qt.Key_Z, Qt.Key_Plus))
@inject
def zoom_in(graph=Inject('gearbox/graph')):
    zoom = graph.get_zoom() + 0.1
    graph.set_zoom(zoom)


@shortcut('graph', (Qt.Key_Z, Qt.Key_Minus))
@inject
def zoom_out(graph=Inject('gearbox/graph')):
    zoom = graph.get_zoom() - 0.2
    graph.set_zoom(zoom)


@shortcut('graph', (Qt.Key_D, Qt.Key_D))
@single_select_action
def describe_definition(node, graph):
    if not isinstance(node, Pipe):
        func = node.model.definition.__wrapped__
        fn = inspect.getfile(func)
        lines, lineno = inspect.getsourcelines(func)
        buff = describe_file(fn, lineno=slice(lineno, lineno + len(lines)))
        show_buffer(buff)


@shortcut('graph', (Qt.Key_D, Qt.SHIFT + Qt.Key_D))
@single_select_action
def describe_definition_extern(node, graph):
    if not isinstance(node, Pipe):
        func = node.model.definition.__wrapped__
        fn = inspect.getfile(func)
        _, lineno = inspect.getsourcelines(func)
        os.system(f'emacsclient -n +{lineno} {fn}')


@shortcut('graph', (Qt.Key_D, Qt.Key_S))
@single_select_action
def describe_rtl_source(node, graph):
    if not isinstance(node, Pipe):
        rtl_source = node.model.rtl_source
        if rtl_source:
            buff = describe_file(rtl_source)
            show_buffer(buff)


@shortcut('graph', (Qt.Key_D, Qt.Key_R))
@single_select_action
def describe_rtl_inst(node, graph):
    if not isinstance(node, Pipe):
        rtl_source = node.model.rtl_source
        if rtl_source:
            buff = describe_file(rtl_source)
            show_buffer(buff)


@shortcut('graph', Qt.Key_Return)
@single_select_action
def toggle_expand(node, graph):
    if isinstance(node, Pipe):
        return

    if node.collapsed:
        node.expand()
    else:
        node.collapse()


@shortcut('graph', Qt.Key_P)
@inject
def send_to_wave(
        graph=Inject('gearbox/graph'), gtkwave=Inject('gearbox/gtkwave/inst')):

    added = []
    selected_item = graph.selected_items()
    for item in selected_item:
        try:
            added.append(gtkwave.show_item(item.model))
        except ItemNotTraced:
            pass

    if (len(selected_item) == 1) and (len(added) == 0):
        message(f'WARNING: {item.model.name} not traced')
    else:
        message('Waves added: ' + ' '.join(added))


shortcut('graph', Qt.Key_S)(step_simulator)
shortcut('graph', Qt.Key_C)(cont_simulator)
shortcut('graph', Qt.Key_Colon)(time_search)


@shortcut('graph', Qt.Key_Slash)
@inject
def node_search(
        minibuffer=Inject('gearbox/minibuffer'),
        graph=Inject('gearbox/graph')):

    items = graph.selected_items()
    if len(items) == 1:
        model = items[0].model
    else:
        model = graph.top.model

    if not model.child:
        model = model.parent

    node_name = get_minibuffer_input(
        message=f'{model.name}/', completer=node_search_completer(model))

    if not node_name:
        return

    node = graph.top.model
    for basename in node_name[1:].split('/'):
        node.view.expand()
        print('basename')
        node = node[basename]

    graph.select(node.view)


class GraphDescription:
    def __init__(self, buff):
        self.buff = buff
        self.buff.view.selection_changed.connect(self.selection_changed)

    def selection_changed(self, selected):
        if selected:
            if hasattr(selected[0].model, 'description'):
                popup_desc(selected[0].model.description, self.buff)

    def delete(self):
        popup_cancel()


class GtkwaveActionsPlugin(GraphBufferPlugin):
    @classmethod
    def bind(cls):
        reg['gearbox/plugins/graph']['TimestepModeline'] = TimestepModeline
        reg['gearbox/plugins/graph']['GraphDescription'] = GraphDescription
