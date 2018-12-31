import os
from pygears.conf import Inject, reg_inject, MayInject
from .graph import GraphVisitor
from jinja2 import Environment, BaseLoader
from pygears.core.hier_node import HierYielderBase

save_file_prolog = """
from pygears.conf import Inject, reg_inject, MayInject, inject_async
from pygears_view.utils import trigger
"""

expand_func_template = """

@reg_inject
def expand(graph_model=Inject('viewer/graph_model')):
  {% if expanded %}
    {% for name in expanded %}
    graph_model['{{name}}'].view.expand()
    {% endfor %}
  {% else %}
    pass
  {% endif %}

"""

save_file_epilog = """
expand()
"""

gtkwave_load_func_template = """

@trigger('viewer/gtkwave_status', 'vcd_loaded')
@reg_inject
def gtkwave_load(gtkwave=Inject('viewer/gtkwave')):
    gtkwave.command(
        'gtkwave::/File/Read_Save_File {{fn}}')

"""


def load_str_template(template):
    return Environment(
        loader=BaseLoader(), trim_blocks=True,
        lstrip_blocks=True).from_string(template)


class GraphStatusSaver(HierYielderBase):
    def NodeModel(self, node):
        if not node.view.collapsed and bool(node.name):
            yield node.name[1:]


@reg_inject
def save_expanded(root=Inject('viewer/graph_model')):
    expanded = list(GraphStatusSaver().visit(root))

    return load_str_template(expand_func_template).render({
        'expanded': expanded
    })


@reg_inject
def save_gtkwave(gtkwave=Inject('viewer/gtkwave')):
    gtkwave.command(
        f'gtkwave::/File/Write_Save_File {get_gtkwave_save_file_path()}')

    return load_str_template(gtkwave_load_func_template).render({
        'fn':
        get_gtkwave_save_file_path()
    })


def save():
    with open(get_save_file_path(), 'w') as f:
        f.write(save_file_prolog)

        f.write(save_expanded())

        f.write(save_gtkwave())

        f.write(save_file_epilog)


@reg_inject
def get_save_file_path(outdir=MayInject('sim/artifact_dir')):
    return os.path.abspath(os.path.join(outdir, 'pygears_view_save.py'))


@reg_inject
def get_gtkwave_save_file_path(outdir=MayInject('sim/artifact_dir')):
    return os.path.abspath(os.path.join(outdir, 'gtkwave.gtkw'))
