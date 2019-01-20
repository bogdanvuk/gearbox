import inspect
from pygears.core.hier_node import NamedHierNode
from pygears.rtl.node import RTLNode
from .node import NodeItem, hier_expand, hier_painter, node_painter
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

        if input_port_model.node is parent.gear:
            input_port = parent.view.outputs[input_port_model.index]
        else:
            input_port = parent[input_port_model.node.basename].view.inputs[
                input_port_model.index]

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
            if not isinstance(child, RTLNode):
                for i in range(len(child.consumers)):
                    n = PipeModel(child, consumer_id=i, parent=self)

                    if parent is not None:
                        n.view.hide()

    @property
    def description(self):
        tooltip = '<b>{}</b><br/><br/>'.format(self.name)
        fmt = pprint.PrettyPrinter(indent=4, width=30).pformat

        table = []
        for name, val in self.gear.params.items():
            row = []
            if name == 'definition':
                val = val.func.__name__
                row = [('style="font-weight:bold"', name),
                       ('style="font-weight:bold"', val)]
            elif inspect.isclass(val) and not is_type(val):
                val = val.__name__
                row = [('style="font-weight:bold"', name), ('', val)]
            elif name not in registry('gear/params/extra').keys():
                row = [('style="font-weight:bold"', name),
                       ('', highlight(fmt(val), 'py', add_style=False))]

            if row:
                table.append(row)

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
