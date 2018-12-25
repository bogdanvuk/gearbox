#!/usr/bin/python
from PySide2.QtCore import Qt
from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, reg_inject, registry
from .main_window import Shortcut
from functools import wraps, partial
from .node_search import node_search_completer
from .pipe import Pipe
import os


def shortcut(domain, shortcut):
    def wrapper(func):
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


def get_node_layer(node):
    for i, layer in enumerate(node.parent.layers):
        if node in layer:
            return i, layer, layer.index(node)
    else:
        return None


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


@shortcut('graph', Qt.Key_S)
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


from pygears.rtl.gear import rtl_from_gear_port


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
