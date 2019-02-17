#!/usr/bin/python
import sys
import inspect
from PySide2.QtCore import Qt
from PySide2 import QtWidgets, QtGui, QtCore
from pygears.conf import Inject, reg_inject, registry, inject_async, bind
from .layout import active_buffer, Window, WindowLayout
from functools import wraps, partial
from .node_search import node_search_completer
from .main_window import Shortcut, message, register_prefix
from .pipe import Pipe
from .saver import save
from .description import describe_text, describe_file, describe_trace
from .gtkwave import ItemNotTraced
from .utils import trigger
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
             minibuffer=Inject('gearbox/minibuffer')):
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

            registry('gearbox/shortcuts').append((domain, shortcut, arg_func))
        else:
            registry('gearbox/shortcuts').append((domain, shortcut, func))

    return wrapper


def single_select_action(func):
    @wraps(func)
    @reg_inject
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
@reg_inject
def zoom_selected(graph=Inject('gearbox/graph')):
    graph.zoom_to_nodes(graph.selected_nodes())


@shortcut('graph', (Qt.Key_Z, Qt.Key_A))
@reg_inject
def zoom_all(graph=Inject('gearbox/graph')):
    graph.fit_all()


@shortcut('graph', Qt.Key_K)
@reg_inject
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


@shortcut('gtkwave', (Qt.Key_T, Qt.Key_M))
def toggle_menu():
    active_buffer().instance.command('gtkwave::toggleStripGUI')


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


@shortcut(None, Qt.CTRL + Qt.Key_H)
@reg_inject
def toggle_help(which_key=Inject('gearbox/which_key')):
    if which_key.isVisible():
        which_key.hide()
    else:
        which_key.show()


class BufferCompleter(QtWidgets.QCompleter):
    @reg_inject
    def __init__(self, layout=Inject('gearbox/layout')):
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


register_prefix(None, Qt.Key_B, 'buffers')


@shortcut(None, (Qt.Key_B, Qt.Key_B))
@reg_inject
def select_buffer(
        buff=Interactive('buffer: ', BufferCompleter),
        layout=Inject('gearbox/layout')):

    if buff is not None:
        layout.current_window.place_buffer(buff)


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
        describe_trace(node.model.rtl.gear.trace)


@shortcut('description', Qt.Key_J)
@reg_inject
def line_down(desc=Inject('gearbox/description')):
    desc.moveCursor(QtGui.QTextCursor.Down)


@shortcut('description', Qt.Key_K)
@reg_inject
def line_up(desc=Inject('gearbox/description')):
    desc.moveCursor(QtGui.QTextCursor.Up)


@shortcut('description', Qt.Key_N)
@reg_inject
def trace_next(desc=Inject('gearbox/description')):
    if desc.trace is not None:
        if desc.trace_pos > 0:
            desc.set_trace_pos(desc.trace_pos - 1)


@shortcut('description', Qt.Key_P)
@reg_inject
def trace_prev(desc=Inject('gearbox/description')):
    if desc.trace is not None:
        if desc.trace_pos < len(desc.trace) - 1:
            desc.set_trace_pos(desc.trace_pos + 1)


@shortcut('description', Qt.Key_E)
@reg_inject
def open_external(desc=Inject('gearbox/description')):
    if desc.fn is not None:
        lineno = desc.lineno
        if isinstance(lineno, slice):
            lineno = lineno.start

        os.system(f'emacsclient -n +{lineno} {desc.fn}')


@shortcut('graph', (Qt.Key_D, Qt.Key_D))
@single_select_action
def describe_definition(node, graph):
    if not isinstance(node, Pipe):
        func = node.model.definition.__wrapped__
        fn = inspect.getfile(func)
        lines, lineno = inspect.getsourcelines(func)
        describe_file(fn, lineno=slice(lineno, lineno + len(lines)))


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
            describe_file(rtl_source)


@shortcut('graph', (Qt.Key_D, Qt.Key_R))
@single_select_action
def describe_rtl_inst(node, graph):
    if not isinstance(node, Pipe):
        rtl_source = node.model.rtl_source
        if rtl_source:
            describe_file(rtl_source)


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
def step_simulator(sim_bridge=Inject('gearbox/sim_bridge')):
    sim_bridge.breakpoints.add(lambda: (True, False))
    if not sim_bridge.running:
        sim_bridge.cont()


@shortcut('graph', Qt.Key_C)
@reg_inject
def cont_simulator(sim_bridge=Inject('gearbox/sim_bridge')):
    sim_bridge.cont()


@shortcut('graph', (Qt.Key_Comma, Qt.Key_W))
def proba():
    print("Hey!!!")


@shortcut('graph', (Qt.Key_Comma, Qt.Key_P))
def proba2():
    print("Hey2!!!")


register_prefix(None, Qt.Key_Q, 'quit')


@shortcut(None, (Qt.Key_Q, Qt.Key_S))
def save_layout():
    save()
    QtWidgets.QApplication.instance().quit()


@shortcut(None, (Qt.Key_Q, Qt.Key_Q))
def quit():
    QtWidgets.QApplication.instance().quit()


register_prefix(None, Qt.Key_W, 'window')


@shortcut(None, (Qt.Key_W, Qt.Key_D))
@reg_inject
def window_delete(layout=Inject('gearbox/layout')):
    if layout.current_layout.win_num > 1:
        window = layout.active_window()
        window.remove()

        next(layout.current_layout.windows()).activate()


@shortcut(None, (Qt.Key_W, Qt.Key_Slash))
@reg_inject
def split_horizontally(layout=Inject('gearbox/layout')):
    window = layout.active_window()
    new_window = window.split_horizontally()

    for b in layout.buffers:
        if not b.visible:
            new_window.place_buffer(b)
            return


@shortcut(None, (Qt.Key_W, Qt.Key_Underscore))
@reg_inject
def split_vertically(layout=Inject('gearbox/layout')):
    window = layout.active_window()
    new_window = window.split_vertically()
    for b in layout.buffers:
        if not b.visible:
            new_window.place_buffer(b)
            return


def change_perc_size(window, diff):
    parent = window.parent
    index = parent.child_index(window)

    prev_stretch = parent.stretch(index)
    cur_stretch = prev_stretch + diff
    prev_remain_stretch = 100 - prev_stretch
    remain_stretch = 100 - cur_stretch

    parent.setStretch(index, cur_stretch)

    for i in range(parent.count()):
        if i != index:
            prev_stretch = parent.stretch(i)
            parent.setStretch(
                i, round(prev_remain_stretch / prev_stretch * remain_stretch))


@shortcut(None, (Qt.Key_W, Qt.Key_Plus))
@reg_inject
def increase_height(layout=Inject('gearbox/layout')):
    change_perc_size(layout.active_window(), +3)


@shortcut(None, (Qt.Key_W, Qt.Key_Minus))
@reg_inject
def decrease_height(layout=Inject('gearbox/layout')):
    change_perc_size(layout.active_window(), -3)


@shortcut(None, (Qt.Key_W, Qt.Key_J))
@reg_inject
def window_down(main=Inject('gearbox/main')):
    def go_topmost_down(window):
        if isinstance(window, Window):
            return window
        else:
            return go_topmost_down(window.child(0))

    def go_down(window, pos):
        if (isinstance(window, WindowLayout) and (window.count() > 1)
                and (window.direction() == QtWidgets.QBoxLayout.TopToBottom)):
            if pos < window.count() - 1:
                return go_topmost_down(window.child(pos + 1))

        else:
            parent = window.parent
            return go_down(parent, parent.child_index(window))

    window = go_down(main.buffers.active_window(), 0)
    if window:
        window.activate()


@shortcut(None, (Qt.Key_W, Qt.Key_K))
@reg_inject
def window_up(main=Inject('gearbox/main')):
    def go_bottommost_down(window):
        if isinstance(window, Window):
            return window
        else:
            return go_bottommost_down(window.child(-1))

    def go_up(window, pos):
        if (isinstance(window, WindowLayout) and (window.count() > 1)
                and (window.direction() == QtWidgets.QBoxLayout.TopToBottom)):
            if pos > 0:
                return go_bottommost_down(window.child(pos - 1))

        else:
            parent = window.parent
            return go_up(parent, parent.child_index(window))

    window = go_up(main.buffers.active_window(), 0)

    if window:
        window.activate()


@shortcut(None, (Qt.Key_W, Qt.Key_L))
@reg_inject
def window_right(main=Inject('gearbox/main')):
    def go_leftmost_down(window):
        if isinstance(window, Window):
            return window
        else:
            return go_leftmost_down(window.child(0))

    def go_right(window, pos):
        if (isinstance(window, WindowLayout) and (window.count() > 1)
                and (window.direction() == QtWidgets.QBoxLayout.LeftToRight)):
            if pos < window.count() - 1:
                return go_leftmost_down(window.child(pos + 1))

        else:
            parent = window.parent
            return go_right(parent, parent.child_index(window))

    window = go_right(main.buffers.active_window(), 0)
    if window:
        window.activate()


@shortcut(None, (Qt.Key_W, Qt.Key_H))
@reg_inject
def window_left(main=Inject('gearbox/main')):
    def go_rightmost_down(window):
        if isinstance(window, Window):
            return window
        else:
            return go_rightmost_down(window.child(-1))

    def go_left(window, pos):
        if (isinstance(window, WindowLayout) and (window.count() > 1)
                and (window.direction() == QtWidgets.QBoxLayout.LeftToRight)):
            if pos > 0:
                return go_rightmost_down(window.child(pos - 1))

        else:
            parent = window.parent
            return go_left(parent, parent.child_index(window))

    window = go_left(main.buffers.active_window(), 0)
    if window:
        window.activate()


@shortcut('graph', Qt.Key_P)
@reg_inject
def send_to_wave(
        graph=Inject('gearbox/graph'), gtkwave=Inject('gearbox/gtkwave')):

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


class ShortcutRepeat(QtCore.QObject):
    def __init__(self, main):
        super().__init__()
        self.last_shortcut = None
        main.shortcut_triggered.connect(self.shortcut_triggered)
        self.repeat_shortcut = Shortcut(
            domain=None, key=Qt.Key_Period, callback=self.repeat)

    def repeat(self):
        if self.last_shortcut:
            self.last_shortcut.activated.emit()

    def shortcut_triggered(self, shortcut):
        if shortcut is not self.repeat_shortcut:
            self.last_shortcut = shortcut


@inject_async
def create_shortcut_repeater(main=Inject('gearbox/main')):
    bind('gearbox/shortcut_repeater', ShortcutRepeat(main))


@reg_inject
def node_expand_toggle(status, node, gtkwave=Inject('gearbox/gtkwave')):
    if status:
        gtkwave.update_pipe_statuses(node.pipes)


@inject_async
def create_node_expand_toggle(graph=Inject('gearbox/graph')):
    graph.node_expand_toggled.connect(node_expand_toggle)


@shortcut('graph', Qt.Key_Slash)
@reg_inject
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


@shortcut(None, Qt.Key_Colon)
@reg_inject
def time_search(
        time=Interactive('Time: '), timekeep=Inject('gearbox/timekeep')):

    try:
        time = int(time)
    except TypeError:
        return

    timekeep.timestep = time


@inject_async
def graph_gtkwave_select_sync(graph=Inject('gearbox/graph')):
    bind('gearbox/graph_gtkwave_select_sync', GraphGtkwaveSelectSync(graph))


# TODO: broken when using gtkwave save file
class GraphGtkwaveSelectSync(QtCore.QObject):
    @reg_inject
    def __init__(self, graph=Inject('gearbox/graph')):
        graph.selection_changed.connect(self.selection_changed)

    @reg_inject
    def selection_changed(self, selected, gtkwave=Inject('gearbox/gtkwave')):

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


@shortcut('graph', (Qt.Key_Z, Qt.Key_Plus))
@reg_inject
def zoom_in(graph=Inject('gearbox/graph')):
    zoom = graph.get_zoom() + 0.1
    graph.set_zoom(zoom)


@shortcut('graph', (Qt.Key_Z, Qt.Key_Minus))
@reg_inject
def zoom_out(graph=Inject('gearbox/graph')):
    zoom = graph.get_zoom() - 0.2
    graph.set_zoom(zoom)


@shortcut(None, (Qt.Key_Space, Qt.Key_F))
@reg_inject
def open_file(sim_bridge=Inject('gearbox/sim_bridge')):
    ret = QtWidgets.QFileDialog.getOpenFileName(
        caption='Open file',
        dir=os.getcwd(),
        filter="PyGears script (*.py);;All files (*)")

    script_fn = ret[0]

    if script_fn:
        registry('gearbox/sim_bridge').invoke_method(
            'run_model', script_fn=script_fn)

        registry('gearbox/sim_bridge').invoke_method('run_sim')
