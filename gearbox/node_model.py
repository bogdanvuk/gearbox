import inspect
import os
import functools
from pygears.sim.modules import SimVerilated, SimSocket
from pygears.core.hier_node import HierVisitorBase
from pygears.core.hier_node import NamedHierNode
from pygears.conf import inject, Inject, reg
from .node import NodeItem, hier_expand, hier_painter, node_painter, minimized_painter
from .node import node_layout, hier_layout, minimized_layout
from pygears.sim.modules.cosim_base import CosimBase
from .pipe import Pipe
from .html_utils import highlight, tabulate, highlight_style
from pygears.core.partial import Partial
from pygears.core.port import InPort, HDLProducer, HDLConsumer
from pygears.typing.pprint import pprint
from pygears.typing import is_type
from pygears.lib import sieve, cast

from .constants import Z_VAL_PIPE


def pprint_Partial(printer, object, stream, indent, allowance, context, level):
    stream.write(object.func.__name__)
    stream.write('()')


pprint.PrettyPrinter._dispatch[Partial.__repr__] = pprint_Partial


@inject
def find_cosim_modules(top=Inject('gear/root')):
    class CosimVisitor(HierVisitorBase):
        @inject
        def __init__(self, sim_map=Inject('sim/map')):
            self.sim_map = sim_map
            self.cosim_modules = []

        def Gear(self, module):
            if isinstance(
                    self.sim_map.get(module, None), (SimVerilated, SimSocket)):
                self.cosim_modules.append(self.sim_map[module])
                return True

    v = CosimVisitor()
    v.visit(top)
    return v.cosim_modules


from .node_abstract import AbstractNodeItem

from .port import PortItem
from pygears.core.port import OutPort
from PySide2 import QtWidgets


class DummyInNode(AbstractNodeItem):
    def __init__(self, parent, index):
        super().__init__()
        self.color = (255, 0, 0)
        self._layout = minimized_layout
        self._input_items = {}
        self._output_items = {}
        self.painter = minimized_painter
        self.outputs = [PortItem(InPort(parent.rtl, index, 'dummy'), self)]
        port_text = QtWidgets.QGraphicsTextItem('dummy', self)
        self._output_items[self.outputs[0]] = port_text

        self.inputs = []
        self._text_item = QtWidgets.QGraphicsTextItem('', self)
        self.layout()

    def paint(self, painter, option, widget):
        self.painter(self, painter, option, widget)

    def layout(self):
        self._layout(self)


class DummyOutNode(AbstractNodeItem):
    def __init__(self, parent, index):
        super().__init__()
        self.color = (255, 0, 0)
        self._layout = minimized_layout
        self._input_items = {}
        self._output_items = {}
        self.painter = minimized_painter
        self.inputs = [PortItem(OutPort(parent.rtl, index, 'dummy'), self)]
        port_text = QtWidgets.QGraphicsTextItem('dummy', self)
        self._input_items[self.inputs[0]] = port_text

        self.outputs = []
        self._text_item = QtWidgets.QGraphicsTextItem('', self)
        self.layout()

    def paint(self, painter, option, widget):
        self.painter(self, painter, option, widget)

    def layout(self):
        self._layout(self)


class PipeModel(NamedHierNode):
    def __init__(self, intf, consumer_id, parent=None):
        super().__init__(parent=parent)

        self.svintf = reg['hdlgen/map'].get(intf, None)

        self.rtl = intf
        self.consumer_id = consumer_id
        output_port_model = intf.producer
        input_port_model = intf.consumers[consumer_id]

        if output_port_model is None:
            breakpoint()

        if output_port_model.gear is parent.rtl:
            try:
                output_port = parent.view.inputs[output_port_model.index]
            except IndexError:
                node = DummyInNode(parent, output_port_model.index)
                parent.view.add_node(node)
                output_port = node.outputs[0]

            # parent.input_int_pipes[output_port_model.index] = self
            parent.input_int_pipes.append(self)
        else:
            output_port = parent[output_port_model.gear.basename].view.outputs[
                output_port_model.index]

            # parent.rtl_map[output_port_model.node].output_ext_pipes[
            #     output_port_model.index] = self
            parent.rtl_map[output_port_model.gear].output_ext_pipes.append(
                self)

        try:
            if input_port_model.gear is parent.rtl:
                try:
                    input_port = parent.view.outputs[input_port_model.index]
                except IndexError:
                    node = DummyOutNode(parent, input_port_model.index)
                    parent.view.add_node(node)
                    input_port = node.inputs[0]

                self.consumer = parent
                self.consumer.output_int_pipes.append(self)
            else:
                input_port = parent[input_port_model.gear.
                                    basename].view.inputs[input_port_model.
                                                          index]
                self.consumer = parent.rtl_map[input_port_model.gear]
                self.consumer.input_ext_pipes.append(self)

        except KeyError:
            import pdb
            pdb.set_trace()

        self.view = Pipe(output_port, input_port, parent.view, self)
        self.parent.view.add_pipe(self.view)

        if self.consumer.related_issues:
            self.set_status('error')
        else:
            self.set_status('empty')

    @inject
    def set_status(self, status, timestep=Inject('gearbox/timekeep')):
        self.status = (timestep, status)
        self.status = status
        self.view.set_status(status)

    @property
    def description(self):
        tooltip = '<b>{}</b><br/>'.format(self.name)
        disp = pprint.pformat(self.rtl.dtype, indent=4, width=30)
        text = highlight(disp, 'py', add_style=False)

        tooltip += text
        return tooltip

    @property
    @functools.lru_cache(maxsize=None)
    def name(self):
        name = self.rtl.name
        if self.svintf is not None:
            name = name.split('.')[0] + '.' + self.svintf.basename

        if len(self.rtl.consumers) > 1:
            return f'{name}_bc_{self.consumer_id}'
        else:
            return name

    @property
    @functools.lru_cache(maxsize=None)
    def basename(self):
        if self.svintf is not None:
            basename = self.svintf.basename
        else:
            basename = self.rtl.basename

        if len(self.rtl.consumers) > 1:
            return f'{basename}_bc_{self.consumer_id}'
        else:
            return basename

    @property
    def hierarchical(self):
        return False


class NodeModel(NamedHierNode):
    def __init__(self, gear, parent=None):
        super().__init__(parent=parent)

        self.rtl = gear

        # self.input_ext_pipes = [None] * len(self.rtl.in_ports)
        # self.output_ext_pipes = [None] * len(self.rtl.out_ports)
        # self.input_int_pipes = [None] * len(self.rtl.in_ports)
        # self.output_int_pipes = [None] * len(self.rtl.out_ports)
        self.input_ext_pipes = []
        self.output_ext_pipes = []
        self.input_int_pipes = []
        self.output_int_pipes = []

        self.rtl_map = {}

        layout = hier_layout if self.hierarchical else node_layout
        painter = None
        try:
            # print(self.definition.__name__)
            # if self.definition.__name__ == 'sieve':
            #     import pdb; pdb.set_trace()

            if self.definition in (sieve.func, cast.func):
                # import pdb
                # pdb.set_trace()
                layout = minimized_layout
                painter = minimized_painter
        except TypeError:
            pass

        self.view = NodeItem(
            gear.basename,
            layout=layout,
            parent=(None if parent is None else parent.view),
            model=self)

        if parent is not None:
            parent.view.add_node(self.view)
            for port in self.rtl.in_ports + self.rtl.out_ports:
                self.view._add_port(port)

        for child in self.rtl.child:
            self.rtl_map[child] = NodeModel(child, self)

            if parent is not None:
                self.rtl_map[child].view.hide()

        self.setup_view(painter=painter)

        for child in self.rtl.local_intfs:
            for i in range(len(child.consumers)):
                if isinstance(child.producer, HDLProducer):
                    continue

                if child.consumers and isinstance(child.consumers[0], HDLConsumer):
                    continue

                if child.producer is None:
                    # TODO: This should be an error?
                    continue

                self.rtl_map[child] = PipeModel(
                    child, consumer_id=i, parent=self)

                if parent is not None:
                    self.rtl_map[child].view.hide()


        # import pdb; pdb.set_trace()
        if self.on_error_path:
            self.set_status('error')
        else:
            self.set_status('empty')

    def __getitem__(self, path):
        return super().__getitem__(path.replace('.', '/'))

    @property
    @inject
    def related_issues(self, issues=Inject('trace/issues')):
        rel_issues = []
        for issue in issues:
            if (self.parent is not None and hasattr(issue, 'gear')
                    and issue.gear is self.rtl.gear):
                rel_issues.append(issue)

        return rel_issues

    @property
    @inject
    def on_error_path(self, sim_bridge=Inject('gearbox/sim_bridge')):
        issue_path = sim_bridge.cur_model_issue_path
        if (self.parent is not None and issue_path
                and self.rtl.gear.has_descendent(issue_path[-1])):
            return True

        return False

    @inject
    def set_status(self, status, timestep=Inject('gearbox/timekeep')):
        self.status = (timestep, status)
        self.view.set_status(status)

    @property
    @inject
    def rtl_source(self, svgen_map=Inject('hdlgen/map')):
        if self.rtl not in svgen_map:
            return None

        svmod = svgen_map[self.rtl]
        if svmod.is_generated:
            for m in find_cosim_modules():
                if m.rtlnode.has_descendent(self.rtl):
                    file_names = svmod.file_name
                    if not isinstance(file_names, tuple):
                        file_names = (file_names, )

                    for fn in file_names:
                        return os.path.join(m.outdir, fn)
        else:
            return svmod.impl_path

    @property
    def definition(self):
        try:
            return self.rtl.params['definition'].func
        except KeyError:
            raise TypeError

    @property
    def description(self):
        tooltip = '<b>{}</b><br/><br/>'.format(self.name)
        pp = pprint.PrettyPrinter(indent=4, width=30)
        fmt = pp.pformat

        def _pprint_list(self, object, stream, indent, allowance, context,
                         level):
            if len(object) > 5:
                object = object[:5] + ['...']

            pprint.PrettyPrinter._pprint_list(self, object, stream, indent,
                                              allowance, context, level)

        pp._dispatch[list.__repr__] = _pprint_list

        table = []
        for name, val in self.rtl.params.items():
            name_style = 'style="font-weight:bold" nowrap'
            val_style = ''

            if name == 'definition':
                val = val.func.__name__
                val_style = 'style="font-weight:bold"'
            elif inspect.isclass(val) and not is_type(val):
                val = val.__name__
            elif name not in reg['gear/params/extra'].keys():
                # if isinstance(val, (list, tuple)) and len(val) > 5:
                #     val = fmt(val[:2]) + '\n...'

                val = highlight(fmt(val), 'py', add_style=False)
            else:
                continue

            table.append([(name_style, name), (val_style, val)])

        table_style = """
<style>
td {
padding-left: 10px;
padding-right: 10px;
}
</style>
        """

        tooltip += table_style
        tooltip += tabulate(table, 'style="padding-right: 10px;"')

        return tooltip

    @property
    def name(self):
        return self.rtl.name

    @property
    def basename(self):
        return self.rtl.basename

    @property
    def hierarchical(self):
        return bool(self.rtl.hierarchical)

    @property
    def pipes(self):
        return list(c for c in self.child if isinstance(c, PipeModel))

    def setup_view(self, painter=None, size_expander=None):

        view = self.view
        view.size_expander = size_expander
        view.painter = painter

        if self.parent is not None:
            if self.hierarchical:
                view.setZValue(Z_VAL_PIPE - 1)

                if view.size_expander is None:
                    view.size_expander = hier_expand

                if view.painter is None:
                    view.painter = hier_painter

            else:
                if view.size_expander is None:
                    view.size_expander = lambda x: None

                if view.painter is None:
                    view.painter = node_painter

        view.setup_done()
