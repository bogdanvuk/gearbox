#!/usr/bin/python
import inspect
from PySide2.QtCore import Qt
from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, reg_inject, registry, inject_async, bind
from .main_window import Shortcut
from functools import wraps, partial
from .node_search import node_search_completer
from .pipe import Pipe
from .saver import save
import os


class Interactive:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class MinibufferWaiter(QtCore.QEventLoop):
    @reg_inject
    def wait(self, minibuffer=Inject('viewer/minibuffer')):
        minibuffer.complete()
        minibuffer.completed.connect(self.completed)
        self.exec_()
        return self.resp

    def completed(self, text):
        self.resp = text
        self.quit()


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
                kwds = {k: MinibufferWaiter().wait() for k in interactives}
                func(**kwds)

            registry('viewer/shortcuts').append((domain, shortcut, arg_func))
        else:
            registry('viewer/shortcuts').append((domain, shortcut, func))

    return wrapper


def single_select_action(func):
    @wraps(func)
    @reg_inject
    def wrapper(graph=Inject('viewer/graph')):
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


@shortcut('graph', (Qt.Key_Z, Qt.Key_Z))
@reg_inject
def zoom_selected(graph=Inject('viewer/graph')):
    graph.zoom_to_nodes(graph.selected_nodes())


@shortcut('graph', (Qt.Key_Z, Qt.Key_A))
@reg_inject
def zoom_all(graph=Inject('viewer/graph')):
    graph.fit_all()


@shortcut('graph', Qt.Key_K)
@reg_inject
def node_up(graph=Inject('viewer/graph')):
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
@reg_inject
def node_down(graph=Inject('viewer/graph')):
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


@shortcut(None, Qt.CTRL + Qt.Key_H)
@reg_inject
def toggle_help(which_key=Inject('viewer/which_key')):
    if which_key.isVisible():
        which_key.hide()
    else:
        which_key.show()


@shortcut(None, Qt.Key_B)
@reg_inject
def next_buffer(main=Inject('viewer/main')):
    main.buffers.next_buffer()


@shortcut('graph', Qt.Key_Return)
@single_select_action
def toggle_expand(node, graph):
    if isinstance(node, Pipe):
        return

    if node.collapsed:
        node.expand()
    else:
        node.collapse()


@shortcut(None, Qt.Key_S)
@reg_inject
def step_simulator(sim_bridge=Inject('viewer/sim_bridge')):
    sim_bridge.breakpoints.add(lambda: (True, False))
    if not sim_bridge.running:
        sim_bridge.cont()


@shortcut('graph', Qt.Key_C)
@reg_inject
def cont_simulator(sim_bridge=Inject('viewer/sim_bridge')):
    sim_bridge.cont()


@shortcut('graph', (Qt.Key_Comma, Qt.Key_W))
def proba():
    print("Hey!!!")


@shortcut('graph', (Qt.Key_Comma, Qt.Key_P))
def proba2():
    print("Hey2!!!")


@shortcut(None, (Qt.Key_Q, Qt.Key_S))
def save_layout():
    save()
    QtWidgets.QApplication.instance().quit()


@shortcut(None, (Qt.Key_Q, Qt.Key_Q))
def quit():
    QtWidgets.QApplication.instance().quit()


@shortcut('graph', Qt.Key_W)
@reg_inject
def send_to_wave(
        graph=Inject('viewer/graph'),
        gtkwave_status=Inject('viewer/gtkwave_status')):

    for pipe in graph.selected_pipes():
        gtkwave_status.show_pipe(pipe)


# @shortcut('graph', Qt.Key_L)
# def list_waves():
#     list_signal_names()


@shortcut('graph', Qt.Key_Slash)
@reg_inject
def node_search(
        minibuffer=Inject('viewer/minibuffer'), graph=Inject('viewer/graph')):
    minibuffer.complete(node_search_completer(graph.top))


@shortcut('graph', Qt.Key_Colon)
@reg_inject
def time_search(time=Interactive(), sim_bridge=Inject('viewer/sim_bridge')):

    time = int(time)

    @reg_inject
    def break_on_timestep(cur_time=Inject('sim/timestep')):
        if cur_time == time:
            return True, False
        else:
            return False, True

    sim_bridge.breakpoints.add(break_on_timestep)
    if not sim_bridge.running:
        sim_bridge.cont()

    print(f"Finished: {time}")


@inject_async
def graph_gtkwave_select_sync(
        graph=Inject('viewer/graph'),
        gtkwave_status=Inject('viewer/gtkwave_status')):
    bind('viewer/graph_gtkwave_select_sync', GraphGtkwaveSelectSync(graph))


class GraphGtkwaveSelectSync(QtCore.QObject):
    @reg_inject
    def __init__(self, graph=Inject('viewer/graph')):
        graph.selection_changed.connect(self.selection_changed)

    @reg_inject
    def selection_changed(self,
                          selected,
                          gtkwave=Inject('viewer/gtkwave'),
                          gtkwave_status=Inject('viewer/gtkwave_status')):

        selected_wave_pipes = []
        for s in selected:
            wave_intf = gtkwave_status.pipes_on_wave.get(s, None)
            if wave_intf:
                selected_wave_pipes.append(wave_intf)

        gtkwave.command('gtkwave::/Edit/UnHighlight_All')
        if selected_wave_pipes:
            gtkwave.command('gtkwave::highlightSignalsFromList {' +
                            " ".join(selected_wave_pipes) + '}')


@inject_async
def graph_gtkwave_select_sync(
        graph=Inject('viewer/graph'),
        gtkwave_status=Inject('viewer/gtkwave_status')):
    bind('viewer/graph_gtkwave_select_sync', GraphGtkwaveSelectSync(graph))


def zoom_in(graph):
    zoom = graph.get_zoom() + 0.1
    graph.set_zoom(zoom)


def zoom_out(graph):
    zoom = graph.get_zoom() - 0.2
    graph.set_zoom(zoom)


def open_session(graph):
    current = graph.current_session()
    viewer = graph.viewer()
    file_path = viewer.load_dialog(current)
    if file_path:
        graph.load_session(file_path)


def save_session(graph):
    current = graph.current_session()
    if current:
        graph.save_session(current)
        msg = 'Session layout saved:\n{}'.format(current)
        viewer = graph.viewer()
        viewer.message_dialog(msg, title='Session Saved')
    else:
        save_session_as(graph)


def save_session_as(graph):
    current = graph.current_session()
    viewer = graph.viewer()
    file_path = viewer.save_dialog(current)
    if file_path:
        graph.save_session(file_path)


def clear_session(graph):
    viewer = graph.viewer()
    if viewer.question_dialog('Clear Session', 'Clear Current Session?'):
        graph.clear_session()


def clear_undo(graph):
    viewer = graph.viewer()
    msg = 'Clear all undo history, Are you sure?'
    if viewer.question_dialog('Clear Undo History', msg):
        graph.undo_stack().clear()
