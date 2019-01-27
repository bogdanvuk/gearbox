import inspect
import os
import functools
from pygears.sim.modules import SimVerilated, SimSocket
from pygears.core.hier_node import HierVisitorBase
from pygears.core.hier_node import NamedHierNode
from pygears.conf import reg_inject, Inject
from pygears.rtl.node import RTLNode
from pygears.rtl.intf import RTLIntf
from .node import NodeItem, hier_expand, hier_painter, node_painter
from pygears.sim.modules.cosim_base import CosimBase
from .pipe import Pipe
from .html_utils import highlight, tabulate, highlight_style
from pygears import registry
from pygears.core.partial import Partial
from pygears.core.port import InPort
from pygears.typing_common.pprint import pprint
from pygears.typing import is_type

from .constants import Z_VAL_PIPE


def pprint_Partial(printer, object, stream, indent, allowance, context, level):
    stream.write(object.func.__name__)
    stream.write('()')


pprint.PrettyPrinter._dispatch[Partial.__repr__] = pprint_Partial


@functools.lru_cache()
@reg_inject
def find_cosim_modules(top=Inject('gear/hier_root')):
    class CosimVisitor(HierVisitorBase):
        @reg_inject
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


class PipeModel(NamedHierNode):
    def __init__(self, intf, consumer_id, parent=None):
        super().__init__(parent=parent)

        self.intf = intf
        self.consumer_id = consumer_id
        output_port_model = intf.producer
        input_port_model = intf.consumers[consumer_id]

        if output_port_model.node is parent.gear:
            output_port = parent.view.inputs[output_port_model.index]
        else:
            output_port = parent[output_port_model.node.basename].view.outputs[
                output_port_model.index]

        try:
            if input_port_model.node is parent.gear:
                input_port = parent.view.outputs[input_port_model.index]
            else:
                input_port = parent[input_port_model.node.
                                    basename].view.inputs[input_port_model.
                                                          index]
        except KeyError:
            import pdb
            pdb.set_trace()

        self.view = Pipe(output_port, input_port, parent.view, self)
        self.parent.view.add_pipe(self.view)

    def set_status(self, status):
        self.view.set_status(status)

    @property
    def description(self):
        tooltip = '<b>{}</b><br/>'.format(self.name)
        disp = pprint.pformat(self.intf.dtype, indent=4, width=30)
        text = highlight(disp, 'py', add_style=False)

        tooltip += text
        return tooltip

    @property
    def name(self):
        return self.intf.name

    @property
    def basename(self):
        return self.intf.basename


class NodeModel(NamedHierNode):
    def __init__(self, gear, parent=None):
        super().__init__(parent=parent)

        self.gear = gear

        self.view = NodeItem(
            gear.basename,
            parent=(None if parent is None else parent.view),
            model=self)

        if parent is not None:
            parent.view.add_node(self.view)
            for port in self.gear.in_ports + self.gear.out_ports:
                self.view._add_port(port)

        for child in self.gear.child:
            if isinstance(child, RTLNode):
                n = NodeModel(child, self)

                if parent is not None:
                    n.view.hide()

        self.setup_view()

        for child in self.gear.child:
            if isinstance(child, RTLIntf):
                for i in range(len(child.consumers)):
                    n = PipeModel(child, consumer_id=i, parent=self)

                    if parent is not None:
                        n.view.hide()

    @property
    @reg_inject
    def rtl_source(self, svgen_map=Inject('svgen/map')):
        if self.gear not in svgen_map:
            return None

        svmod = svgen_map[self.gear]
        if svmod.is_generated:
            for m in find_cosim_modules():
                if m.rtlnode.is_descendent(self.gear):
                    file_names = svmod.sv_file_name
                    if not isinstance(file_names, tuple):
                        file_names = (file_names, )

                    for fn in file_names:
                        return os.path.join(m.outdir, fn)
        else:
            return svmod.sv_impl_path

    @property
    def definition(self):
        return self.gear.params['definition'].func

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
        for name, val in self.gear.params.items():
            name_style = 'style="font-weight:bold" nowrap'
            val_style = ''

            if name == 'definition':
                val = val.func.__name__
                val_style = 'style="font-weight:bold"'
            elif inspect.isclass(val) and not is_type(val):
                val = val.__name__
            elif name not in registry('gear/params/extra').keys():
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

        # disp = pprint.pformat(self.intf.dtype, indent=4, width=30)
        # from .html_utils import highlight
        # # text = highlight(disp, 'py', style='default')
        # text = highlight(disp, 'py')
        # print(text)

        # tooltip += text
        # tooltip += '<br/>{}<br/>'.format(
        #     pprint.pformat(self.model.intf.dtype, indent=4, width=30))
        # return highlight_style(tooltip)
        return tooltip

    @property
    def name(self):
        return self.gear.name

    @property
    def basename(self):
        return self.gear.basename

    @property
    def hierarchical(self):
        return bool(self.gear.is_hierarchical)

    def setup_view(self):

        view = self.view

        if self.parent is not None:
            if self.hierarchical:
                view.setZValue(Z_VAL_PIPE - 1)
                view.size_expander = hier_expand
                view.painter = hier_painter
            else:
                view.size_expander = lambda x: None
                view.painter = node_painter

        view.setup_done()

        # for graph_node in self.child:
        #     child = graph_node.gear

        #     if child.child:
        #         graph_node.view.collapse()

        #     for port in child.in_ports:
        #         producer = port.producer.producer

        #         if producer.gear is self.gear:
        #             src_port = self.view.inputs[producer.index]
        #             dest_port = graph_node.view.inputs[port.index]
        #             self.view.connect(src_port, dest_port)

        #     for port in child.out_ports:
        #         for consumer in port.consumer.consumers:

        #             if consumer.gear is self.gear:
        #                 consumer_graph_node = self.view
        #             else:
        #                 consumer_graph_node = self[consumer.gear.basename].view

        #             if consumer_graph_node:
        #                 src_port = graph_node.view.outputs[port.index]

        #                 if isinstance(consumer, InPort):
        #                     dest_port = consumer_graph_node.inputs[consumer.
        #                                                            index]
        #                 else:
        #                     dest_port = consumer_graph_node.outputs[consumer.
        #                                                             index]

        #                 self.view.connect(src_port, dest_port)
