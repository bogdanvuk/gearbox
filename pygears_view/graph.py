#!/usr/bin/python
import json
import os
import re

from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtGui import QClipboard, QKeySequence
from PySide2.QtWidgets import QAction, QUndoStack, QShortcut, QLabel

# from .actions import setup_actions
from .commands import (NodeAddedCmd, NodeRemovedCmd, NodeMovedCmd,
                       PortConnectedCmd)
from .node import NodeItem
from .viewer import NodeViewer

from grandalf.layouts import SugiyamaLayout
from grandalf.graphs import Vertex, Edge, Graph

from .minibuffer import Minibuffer
from .gtkwave import GtkWave, GtkWaveProc
from .which_key import WhichKey
from .node_search import node_search_completer

from pygears.conf import PluginBase, registry, safe_bind


class defaultview:
    def __init__(self, w, h):
        self.w = h
        self.h = w


class NodeGraphModel(object):
    def __init__(self):
        self.nodes = {}
        self.session = ''
        self.acyclic = True


def _find_rec(path, root):
    parts = path.split("/")

    # if parts[0] == '..':
    #     return _find_rec("/".join(parts[1:]), root.parent)

    for node in root._nodes:
        child = node.model
        if hasattr(child, 'basename') and child.basename == parts[0]:
            break
    else:
        raise Exception()

    if len(parts) == 1:
        return [node]
    else:
        path_rest = "/".join(parts[1:])
        if path_rest:
            return [node] + _find_rec("/".join(parts[1:]), node)
        else:
            return [node]


def find_node_by_path(root, path):
    return _find_rec(path, root)


class BufferStack(QtWidgets.QStackedLayout):
    def __init__(self, graph, parent=None):
        super().__init__(parent)
        self.setMargin(0)
        self.graph = graph
        self.setContentsMargins(0, 0, 0, 0)
        self._buffers = {}

    def __setitem__(self, key, value):
        self._buffers[key] = value
        self.addWidget(value)
        # value.installEventFilter(self.graph)

    def __getitem__(self, key):
        return self._buffers[key]

    @property
    def current_name(self):
        return list(self._buffers.keys())[self.currentIndex()]

    def next_buffer(self):
        next_id = self.currentIndex() + 1
        if next_id >= len(self._buffers):
            self.setCurrentIndex(0)
        else:
            self.setCurrentIndex(next_id)

        self.graph.domain_changed.emit(self.current_name)


class Shortcut(QtCore.QObject):
    def __init__(self, graph, domain, key, callback):
        self._qshortcut = QShortcut(QKeySequence(key), graph)
        self._qshortcut.activated.connect(callback)
        self._qshortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        self._qshortcut.setWhatsThis(callback.__name__)
        self.domain = domain
        self.key = key
        self.callback = callback
        graph.domain_changed.connect(self.domain_changed)

    @property
    def enabled(self):
        return self._qshortcut.isEnabled()

    def domain_changed(self, domain):
        print(f'{domain} ?= {self.domain}')
        if (self.domain is None) or (self.domain == domain):
            self._qshortcut.setEnabled(True)
        else:
            print('Shortcut disabled')
            self._qshortcut.setEnabled(False)


class NodeGraph(QtWidgets.QMainWindow):

    node_selected = QtCore.Signal(NodeItem)
    key_cancel = QtCore.Signal()
    domain_changed = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        safe_bind('graph/graph', self)

        self._model = NodeGraphModel()
        self._viewer = NodeViewer()
        self._undo_stack = QUndoStack(self)
        self.buffers = {}

        vbox = QtWidgets.QVBoxLayout()
        vbox.setSpacing(0)
        vbox.setMargin(0)
        vbox.setContentsMargins(0, 0, 0, 0)

        self.buffers = BufferStack(graph=self)
        vbox.addLayout(self.buffers)

        # self.gtkwave = GtkWave()

        self.buffers['graph'] = self._viewer

        mainWidget = QtWidgets.QWidget()
        mainWidget.setLayout(vbox)
        mainWidget.setContentsMargins(0, 0, 0, 0)

        self.which_key = WhichKey()
        vbox.addWidget(self.which_key)

        self.minibuffer = Minibuffer()
        self.minibuffer.completed.connect(self._minibuffer_completed)

        vbox.addWidget(self.minibuffer)

        self.setCentralWidget(mainWidget)

        self._init_actions()
        self._wire_signals()
        self._nodes = []

        self.shortcuts = [
            Shortcut(self, domain, key, callback)
            for domain, key, callback in registry('graph/shortcuts')
        ]

    # def eventFilter(self, obj, event):
    #     # print(f"Graph: {event.type()}")
    #     if (event.type() == QtCore.QEvent.KeyPress) or (
    #             event.type() == QtCore.QEvent.ShortcutOverride):
    #     # if event.type() == QtCore.QEvent.KeyPress:
    #         key = QtGui.QKeySequence(event.key() + int(event.modifiers())).toString()

    #         print(f"Graph: {event.type()}")
    #         print(f"   {key} = {event.key()} + {int(event.modifiers())}")
    #         for shortcut, callback in registry('graph/shortcuts'):
    #             if shortcut == event.key() + int(event.modifiers()):
    #                 callback()
    #                 print("Accept in main")
    #                 if event.type() == QtCore.QEvent.ShortcutOverride:
    #                     event.accept()
    #                     return super().eventFilter(obj, event)
    #                 else:
    #                     return True

    #         # if self.buffers.current_name == 'gtkwave':
    #         #     print("Dispatch to gtkwave")
    #         #     self.gtkwave.keyPressEvent(event)
    #         #     return True

    #     return super().eventFilter(obj, event)

    def _wire_signals(self):
        self._viewer.connection_changed.connect(self._on_connection_changed)
        self._viewer.node_selected.connect(self._on_node_selected)

    def _init_actions(self):
        QShortcut(
            QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_G),
            self._viewer).activated.connect(self._key_cancel_event)

    def _key_cancel_event(self):
        self.key_cancel.emit()

    def _minibuffer_completed(self, text):
        try:
            node_path = find_node_by_path(self.top, text)
            for node in node_path[:-1]:
                node.expand()
        except:
            for node in self.selected_nodes():
                node.setSelected(False)
            return

        for node in self.selected_nodes():
            node.setSelected(False)

        node_path[-1].setSelected(True)
        self._viewer.ensureVisible(node_path[-1])

    def _toggle_tab_search(self):
        """
        toggle the tab search widget.
        """
        self.minibuffer.complete(node_search_completer(self.top))

    def _on_node_selected(self, node_id):
        """
        called when a node in the viewer is selected on left click.
        (emits the node object when the node is clicked)

        Args:
            node_id (str): node id emitted by the viewer.
        """
        node = self.get_node_by_id(node_id)
        self.node_selected.emit(node)

    def _on_search_triggered(self, node_type, pos):
        """
        called when the tab search widget is triggered in the viewer.

        Args:
            node_type (str): node identifier.
            pos (tuple): x,y position for the node.
        """
        self.create_node(node_type, pos=pos)

    def _on_connection_changed(self, disconnected, connected):
        """
        called when a pipe connection has been changed in the viewer.

        Args:
            disconnected (list[list[widgets.port.PortItem]):
                pair list of port view items.
            connected (list[list[widgets.port.PortItem]]):
                pair list of port view items.
        """
        if not (disconnected or connected):
            return

        label = 'connected node(s)' if connected else 'disconnected node(s)'
        ptypes = {'in': 'inputs', 'out': 'outputs'}

        self._undo_stack.beginMacro(label)
        for p1_view, p2_view in disconnected:
            node1 = self._model.nodes[p1_view.node.id]
            node2 = self._model.nodes[p2_view.node.id]
            port1 = getattr(node1, ptypes[p1_view.port_type])()[p1_view.name]
            port2 = getattr(node2, ptypes[p2_view.port_type])()[p2_view.name]
            port1.disconnect_from(port2)
        for p1_view, p2_view in connected:
            node1 = self._model.nodes[p1_view.node.id]
            node2 = self._model.nodes[p2_view.node.id]
            port1 = getattr(node1, ptypes[p1_view.port_type])()[p1_view.name]
            port2 = getattr(node2, ptypes[p2_view.port_type])()[p2_view.name]
            port1.connect_to(port2)
        self._undo_stack.endMacro()

    @property
    def model(self):
        """
        Return the node graph model.

        Returns:
            NodeGraphModel: model object.
        """
        return self._model

    # def show(self):
    #     """
    #     Show node graph viewer widget.
    #     """
    #     self._viewer.show()

    def hide(self):
        """
        Hide node graph viewer widget.
        """
        self._viewer.hide()

    def close(self):
        """
        Close node graph viewer widget.
        """
        self._viewer.close()

    def viewer(self):
        """
        Return the node graph viewer widget object.

        Returns:
            NodeGraphQt.widgets.viewer.NodeViewer: viewer widget.
        """
        return self._viewer

    def scene(self):
        """
        Return the scene object.

        Returns:
            NodeGraphQt.widgets.scene.NodeScene: node scene.
        """
        return self._viewer.scene()

    def undo_stack(self):
        """
        Returns the undo stack used in the node graph

        Returns:
            QUndoStack: undo stack.
        """
        return self._undo_stack

    def begin_undo(self, name='undo'):
        """
        Start of an undo block followed by a end_undo().

        Args:
            name (str): name for the undo block.
        """
        self._undo_stack.beginMacro(name)

    def end_undo(self):
        """
        End of an undo block started by begin_undo().
        """
        self._undo_stack.endMacro()

    def context_menu(self):
        """
        Returns a node graph context menu object.

        Returns:
            ContextMenu: node graph context menu object instance.
        """
        return self._viewer.context_menu()

    def acyclic(self):
        """
        Returns true if the current node graph is acyclic.

        Returns:
            bool: true if acyclic.
        """
        return self._model.acyclic

    def set_acyclic(self, mode=True):
        """
        Set the node graph to be acyclic or not. (default=True)

        Args:
            mode (bool): false to disable acyclic.
        """
        self._model.acyclic = mode
        self._viewer.acyclic = mode

    def set_pipe_layout(self, layout='curved'):
        """
        Set node graph pipes to be drawn straight or curved by default
        all pipes are set curved. (default='curved')

        Args:
            layout (str): 'straight' or 'curved'
        """
        self._viewer.set_pipe_layout(layout)

    def fit_to_selection(self):
        """
        Sets the zoom level to fit selected nodes.
        If no nodes are selected then all nodes in the graph will be framed.
        """
        nodes = self.selected_nodes() or self.all_nodes()
        if not nodes:
            return
        self._viewer.zoom_to_nodes([n for n in nodes])

    def reset_zoom(self):
        """
        Reset the zoom level
        """
        self._viewer.reset_zoom()

    def set_zoom(self, zoom=0):
        """
        Set the zoom factor of the Node Graph the default is 0.0

        Args:
            zoom (float): zoom factor max zoom out -0.9 max zoom in 2.0
        """
        self._viewer.set_zoom(zoom)

    def get_zoom(self):
        """
        Get the current zoom level of the node graph.

        Returns:
            float: the current zoom level.
        """
        return self._viewer.get_zoom()

    def fit_all(self):
        self._viewer.zoom_to_nodes(self.top._nodes)

    def center_on(self, nodes=None):
        """
        Center the node graph on the given nodes or all nodes by default.

        Args:
            nodes (list[NodeGraphQt.Node]): a list of nodes.
        """
        self._viewer.center_selection(nodes)

    def center_selection(self):
        """
        Center the node graph on the current selected nodes.
        """
        nodes = self._viewer.selected_nodes()
        self._viewer.center_selection(nodes)

    def get_nodes(self, node):
        return self._nodes

    def delete_nodes(self, nodes):
        """
        Remove a list of nodes from the node graph.

        Args:
            nodes (list[NodeGraphQt.Node]): list of node instances.
        """
        self._undo_stack.beginMacro('deleted nodes')
        [self.delete_node(n) for n in nodes]
        self._undo_stack.endMacro()

    def all_nodes(self):
        """
        Return all nodes in the node graph.

        Returns:
            list[NodeGraphQt.Node]: list of nodes.
        """
        return list(self._model.nodes.values())

    def select(self, node):

        for n in self._viewer.selected_nodes():
            n.selected = False

        node.selected = True

    def selected_nodes(self):
        """
        Return all selected nodes that are in the node graph.

        Returns:
            list[NodeGraphQt.Node]: list of nodes.
        """
        return self._viewer.selected_nodes()

    def select_all(self):
        """
        Select all nodes in the current node graph.
        """
        self._undo_stack.beginMacro('select all')
        for node in self.all_nodes():
            node.set_selected(True)
        self._undo_stack.endMacro()

    def clear_selection(self):
        """
        Clears the selection in the node graph.
        """
        self._undo_stack.beginMacro('deselected nodes')
        for node in self.all_nodes():
            node.set_selected(False)
        self._undo_stack.endMacro()

    def get_node_by_id(self, node_id=None):
        """
        Get the node object by it's id.

        Args:
            node_id (str): node id

        Returns:
            NodeGraphQt.NodeObject: node object.
        """
        return self._model.nodes.get(node_id)

    def get_node_by_name(self, name):
        """
        Returns node object that matches the name.

        Args:
            name (str): name of the node.
        Returns:
            NodeGraphQt.Node: node object.
        """
        for node_id, node in self._model.nodes.items():
            if node.name() == name:
                return node

    def get_unique_name(self, name):
        """
        return a unique node name for the node.

        Args:
            name (str): node name.

        Returns:
            str: unique node name.
        """
        name = ' '.join(name.split())
        node_names = [n.name() for n in self.all_nodes()]
        if name not in node_names:
            return name

        regex = re.compile('[\w ]+(?: )*(\d+)')
        search = regex.search(name)
        if not search:
            for x in range(1, len(node_names) + 1):
                new_name = '{} {}'.format(name, x)
                if new_name not in node_names:
                    return new_name

        version = search.group(1)
        name = name[:len(version) * -1].strip()
        for x in range(1, len(node_names) + 1):
            new_name = '{} {}'.format(name, x)
            if new_name not in node_names:
                return new_name

    def current_session(self):
        """
        returns the file path to the currently loaded session.

        Returns:
            str: path to the currently loaded session
        """
        return self._model.session

    def clear_session(self):
        """
        clear the loaded node layout session.
        """
        for n in self.all_nodes():
            self.delete_node(n)
        self._undo_stack.clear()
        self._model.session = None

    def _serialize(self, nodes):
        """
        serialize nodes to a dict.

        Args:
            nodes (list[NodeGraphQt.Nodes]): list of node instances.

        Returns:
            dict: serialized data.
        """
        serial_data = {'nodes': {}, 'connections': []}
        nodes_data = {}
        for n in nodes:

            # update the node model.
            n.update_model()

            nodes_data.update(n.model.to_dict)

        for n_id, n_data in nodes_data.items():
            serial_data['nodes'][n_id] = n_data

            inputs = n_data.pop('inputs') if n_data.get('inputs') else {}
            outputs = n_data.pop('outputs') if n_data.get('outputs') else {}

            for pname, conn_data in inputs.items():
                for conn_id, prt_names in conn_data.items():
                    for conn_prt in prt_names:
                        pipe = {
                            'in': [n_id, pname],
                            'out': [conn_id, conn_prt]
                        }
                        if pipe not in serial_data['connections']:
                            serial_data['connections'].append(pipe)

            for pname, conn_data in outputs.items():
                for conn_id, prt_names in conn_data.items():
                    for conn_prt in prt_names:
                        pipe = {
                            'out': [n_id, pname],
                            'in': [conn_id, conn_prt]
                        }
                        if pipe not in serial_data['connections']:
                            serial_data['connections'].append(pipe)

        if not serial_data['connections']:
            serial_data.pop('connections')

        return serial_data

    def _deserialize(self, data, relative_pos=False, pos=None):
        """
        deserialize node data.

        Args:
            data (dict): node data.
            relative_pos (bool): position node relative to the cursor.

        Returns:
            list[NodeGraphQt.Nodes]: list of node instances.
        """
        nodes = {}

        # build the nodes.
        for n_id, n_data in data.get('nodes', {}).items():
            identifier = n_data['type']
            NodeInstance = NodeVendor.create_node_instance(identifier)
            if NodeInstance:
                node = NodeInstance()
                node._graph = self

                name = self.get_unique_name(n_data.get('name', node.NODE_NAME))
                n_data['name'] = name

                # set properties.
                for prop, val in node.model.properties.items():
                    if prop in n_data.keys():
                        setattr(node.model, prop, n_data[prop])

                # set custom properties.
                for prop, val in n_data.get('custom', {}).items():
                    if prop in node.model.custom_properties.keys():
                        node.model.custom_properties[prop] = val

                node.update()

                self._undo_stack.push(
                    NodeAddedCmd(self, node, n_data.get('pos')))
                nodes[n_id] = node

        # build the connections.
        for connection in data.get('connections', []):
            nid, pname = connection.get('in', ('', ''))
            in_node = nodes.get(nid)
            if not in_node:
                continue
            in_port = in_node.inputs().get(pname) if in_node else None

            nid, pname = connection.get('out', ('', ''))
            out_node = nodes.get(nid)
            if not out_node:
                continue
            out_port = out_node.outputs().get(pname) if out_node else None

            if in_port and out_port:
                self._undo_stack.push(PortConnectedCmd(in_port, out_port))

        node_objs = list(nodes.values())
        if relative_pos:
            self._viewer.move_nodes([n.view for n in node_objs])
            [setattr(n.model, 'pos', n.view.pos) for n in node_objs]
        elif pos:
            self._viewer.move_nodes([n.view for n in node_objs], pos=pos)

        return node_objs

    def save_session(self, file_path):
        """
        Saves the current node graph session layout to a JSON formatted file.

        Args:
            file_path (str): path to the saved node layout.
        """
        serliazed_data = self._serialize(self.selected_nodes())
        file_path = file_path.strip()
        with open(file_path, 'w') as file_out:
            json.dump(
                serliazed_data, file_out, indent=2, separators=(',', ':'))

    def load_session(self, file_path):
        """
        Load node graph session layout file.

        Args:
            file_path (str): path to the serialized layout file.
        """
        file_path = file_path.strip()
        if not os.path.isfile(file_path):
            raise IOError('file does not exist.')

        self.clear_session()

        try:
            with open(file_path) as data_file:
                layout_data = json.load(data_file)
        except Exception as e:
            layout_data = None
            print('Cannot read data from file.\n{}'.format(e))

        if not layout_data:
            return

        self._deserialize(layout_data)
        self._undo_stack.clear()
        self._model.session = file_path

    def copy_nodes(self, nodes=None):
        """
        copy nodes to the clipboard by default this method copies
        the selected nodes from the node graph.

        Args:
            nodes (list[NodeGraphQt.Node]): list of node instances.
        """
        nodes = nodes or self.selected_nodes()
        if not nodes:
            return False
        clipboard = QClipboard()
        serial_data = self._serialize(nodes)
        serial_str = json.dumps(serial_data)
        if serial_str:
            clipboard.setText(serial_str)
            return True
        return False

    def paste_nodes(self):
        """
        Pastes nodes from the clipboard.
        """
        clipboard = QClipboard()
        cb_string = clipboard.text()
        if not cb_string:
            return

        self._undo_stack.beginMacro('pasted nodes')
        serial_data = json.loads(cb_string)
        self.clear_selection()
        nodes = self._deserialize(serial_data, True)
        [n.set_selected(True) for n in nodes]
        self._undo_stack.endMacro()

    def duplicate_nodes(self, nodes):
        """
        Create duplicates nodes.

        Args:
            nodes (list[NodeGraphQt.Node]): list of node objects.
        Returns:
            list[NodeGraphQt.Node]: list of duplicated node instances.
        """
        if not nodes:
            return

        self._undo_stack.beginMacro('duplicated nodes')

        self.clear_selection()
        serial = self._serialize(nodes)
        new_nodes = self._deserialize(serial)
        offset = 50
        for n in new_nodes:
            x, y = n.pos()
            n.set_pos(x + offset, y + offset)
            n.set_property('selected', True)

        self._undo_stack.endMacro()
        return new_nodes

    def disable_nodes(self, nodes, mode=None):
        """
        Disable/Enable specified nodes.

        Args:
            nodes (list[NodeGraphQt.Node]): list of node instances.
            mode (bool): (optional) disable state of the nodes.
        """
        if not nodes:
            return
        if mode is None:
            mode = not nodes[0].disabled()
        if len(nodes) > 1:
            text = {False: 'enabled', True: 'disabled'}[mode]
            text = '{} ({}) nodes'.format(text, len(nodes))
            self._undo_stack.beginMacro(text)
            [n.set_disabled(mode) for n in nodes]
            self._undo_stack.endMacro()
            return
        nodes[0].set_disabled(mode)


class GearGraphPlugin(PluginBase):
    @classmethod
    def bind(cls):
        safe_bind('graph/shortcuts', [])
