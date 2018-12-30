import os
from pygears.conf import Inject, reg_inject, MayInject
from .graph import GraphVisitor
from jinja2 import Environment, BaseLoader
from pygears.core.hier_node import HierYielderBase

save_file_prolog = """
from pygears.conf import Inject, reg_inject, MayInject
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


class GraphStatusSaver(HierYielderBase):
    def NodeModel(self, node):
        if not node.view.collapsed and bool(node.name):
            yield node.name[1:]


@reg_inject
def save_expanded(root=Inject('viewer/graph_model')):
    expanded = list(GraphStatusSaver().visit(root))

    rtemplate = Environment(
        loader=BaseLoader(), trim_blocks=True,
        lstrip_blocks=True).from_string(expand_func_template)
    return rtemplate.render({'expanded': expanded})


def save():
    with open(get_save_file_path(), 'w') as f:
        f.write(save_file_prolog)

        f.write(save_expanded())

        f.write(save_file_epilog)


@reg_inject
def get_save_file_path(outdir=MayInject('sim/artifact_dir')):
    return os.path.join(outdir, 'pygears_view_save.py')
