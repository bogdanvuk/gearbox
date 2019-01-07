#!/usr/bin/python
import inspect
from PySide2.QtCore import Qt
from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, reg_inject, registry, inject_async, bind
from .layout import active_buffer, BufferLayout
from functools import wraps, partial
from .node_search import node_search_completer
from .pipe import Pipe
from .saver import save
import os


class Interactive:
    def __init__(self, message=None, completer=lambda: None):
        self.message = message
        self.completer = completer


class MinibufferWaiter(QtCore.QEventLoop):
    @reg_inject
    def wait(self,
             message=None,
             completer=None,
             minibuffer=Inject('viewer/minibuffer')):
        minibuffer.complete(message, completer)
        minibuffer.completed.connect(self.completed)
        self.exec_()
        return self.resp

    def completed(self, text):
        self.resp = text
        self.quit()


def get_minibuffer_input(message=None, completer=None, text=None):
    return MinibufferWaiter().wait(message, completer)


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
                kwds = {
                    k: get_minibuffer_input(v.message, v.completer())
                    for k, v in interactives.items()
                }
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


@shortcut('gtkwave', Qt.Key_J)
def trace_down():
    active_buffer().instance.command('trace_down')


@shortcut('gtkwave', Qt.Key_K)
def trace_up():
    active_buffer().instance.command('trace_up')


@shortcut('gtkwave', Qt.Key_Return)
def trace_toggle():
    active_buffer().instance.command('gtkwave::/Edit/Toggle_Group_Open|Close')


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


class BufferCompleter(QtWidgets.QCompleter):
    @reg_inject
    def __init__(self, layout=Inject('viewer/layout')):
        super().__init__()

        self.layout = layout
        self.setCompletionMode(self.PopupCompletion)
        self.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        model = QtCore.QStringListModel()
        completion_list = [b.name for b in layout.buffers]
        model.setStringList(completion_list)
        self.setModel(model)

    def get_result(self, text):
        return self.layout.get_buffer_by_name(text)


@shortcut(None, (Qt.Key_B, Qt.Key_B))
@reg_inject
def select_buffer(
        buff=Interactive('buffer: ', BufferCompleter),
        layout=Inject('viewer/layout')):

    if buff is not None:
        layout.current_window.place_buffer(buff)


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


@shortcut(None, (Qt.Key_W, Qt.Key_Slash))
@reg_inject
def split_horizontally(main=Inject('viewer/main')):
    window = main.buffers.active_window()
    window.split_horizontally()


@shortcut(None, (Qt.Key_W, Qt.Key_Minus))
@reg_inject
def split_vertically(layout=Inject('viewer/layout')):
    window = layout.active_window()
    new_window = window.split_vertically()
    for b in layout.buffers:
        if not b.visible:
            new_window.place_buffer(b)
            return


@shortcut(None, (Qt.Key_W, Qt.Key_L))
@reg_inject
def window_right(main=Inject('viewer/main')):
    def go_leftmost_down(window):
        if isinstance(window, BufferLayout):
            return window
        else:
            return go_leftmost_down(window.child(0))

    def go_right(window, pos):
        if (window.size > 1) and (
                window.direction() == QtWidgets.QBoxLayout.LeftToRight):
            if pos < window.size - 1:
                return go_leftmost_down(window.child(pos + 1))

        else:
            parent = window.parent
            return go_right(parent, parent.child_index(window))

    window = go_right(main.buffers.active_window(), 0)
    window.activate()


@shortcut(None, (Qt.Key_W, Qt.Key_J))
@reg_inject
def window_down(main=Inject('viewer/main')):
    def go_topmost_down(window):
        if isinstance(window, BufferLayout):
            return window
        else:
            return go_topmost_down(window.child(0))

    def go_down(window, pos):
        if (window.size > 1) and (
                window.direction() == QtWidgets.QBoxLayout.TopToBottom):
            if pos < window.size - 1:
                return go_topmost_down(window.child(pos + 1))

        else:
            parent = window.parent
            return go_down(parent, parent.child_index(window))

    window = go_down(main.buffers.active_window(), 0)
    window.activate()


@shortcut(None, (Qt.Key_W, Qt.Key_K))
@reg_inject
def window_up(main=Inject('viewer/main')):
    def go_bottommost_down(window):
        if isinstance(window, BufferLayout):
            return window
        else:
            return go_bottommost_down(window.child(-1))

    def go_up(window, pos):
        if (window.size > 1) and (
                window.direction() == QtWidgets.QBoxLayout.TopToBottom):
            if pos > 0:
                return go_bottommost_down(window.child(pos - 1))

        else:
            parent = window.parent
            return go_up(parent, parent.child_index(window))

    window = go_up(main.buffers.active_window(), 0)
    window.activate()


@shortcut('graph', Qt.Key_P)
@reg_inject
def send_to_wave(
        graph=Inject('viewer/graph'), gtkwave=Inject('viewer/gtkwave')):

    for pipe in graph.selected_pipes():
        gtkwave.show_pipe(pipe)


# @shortcut('graph', Qt.Key_L)
# def list_waves():
#     list_signal_names()


@shortcut('graph', Qt.Key_Slash)
@reg_inject
def node_search(
        minibuffer=Inject('viewer/minibuffer'), graph=Inject('viewer/graph')):

    items = graph.selected_items()
    if len(items) == 1:
        model = items[0].model
    else:
        model = graph.top.model

    if not model.child:
        model = model.parent

    node_name = get_minibuffer_input(
        message=f'{model.name}/', completer=node_search_completer(model))

    node = graph.top.model
    for basename in node_name[1:].split('/'):
        node.view.expand()
        print('basename')
        node = node[basename]

    graph.select(node.view)

    # try:
    #     node = graph.top[node_name]
    # except KeyError:
    #     pass

    # try:
    #     node_path = find_node_by_path(graph.top, text)
    #     for node in node_path[:-1]:
    #         node.expand()
    # except:
    #     for node in graph.selected_nodes():
    #         node.setSelected(False)
    #     return

    # for node in graph.selected_nodes():
    #     node.setSelected(False)

    # node_path[-1].setSelected(True)
    # graph.ensureVisible(node_path[-1])

    # print(resp)

    # minibuffer.complete(
    #     message=f'{model.name}/', completer=node_search_completer(model))


@shortcut('graph', Qt.Key_Colon)
@reg_inject
def time_search(
        time=Interactive('Time: '), sim_bridge=Inject('viewer/sim_bridge')):

    if time is None:
        return

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
def graph_gtkwave_select_sync(graph=Inject('viewer/graph')):
    bind('viewer/graph_gtkwave_select_sync', GraphGtkwaveSelectSync(graph))


# TODO: broken when using gtkwave save file
class GraphGtkwaveSelectSync(QtCore.QObject):
    @reg_inject
    def __init__(self, graph=Inject('viewer/graph')):
        graph.selection_changed.connect(self.selection_changed)

    @reg_inject
    def selection_changed(self, selected, gtkwave=Inject('viewer/gtkwave')):

        selected_wave_pipes = {}
        for s in selected:
            gtkwave_intf = gtkwave.pipe_gtkwave_intf(s)
            if gtkwave_intf:
                if gtkwave_intf not in selected_wave_pipes:
                    selected_wave_pipes[gtkwave_intf] = []
            else:
                continue

            wave_intf = gtkwave_intf.pipes_on_wave.get(s, None)
            if wave_intf:
                selected_wave_pipes[gtkwave_intf].append(wave_intf)

        for intf, wave_list in selected_wave_pipes.items():
            intf.gtkwave_intf.command([
                'gtkwave::/Edit/UnHighlight_All',
                f'gtkwave::highlightSignalsFromList {{{" ".join(wave_list)}}}'
            ])


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
