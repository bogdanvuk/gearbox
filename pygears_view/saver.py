import os
from pygears.conf import Inject, reg_inject, MayInject
from .graph import GraphVisitor
from jinja2 import Environment, BaseLoader
from pygears.core.hier_node import HierYielderBase
from .layout import Window

save_file_prolog = """
from pygears.conf import Inject, reg_inject, MayInject, inject_async
from pygears_view.utils import trigger
from pygears_view.layout import Window, WindowLayout
from PySide2 import QtWidgets
from functools import partial
"""

expand_func_template = """

@reg_inject
def expand(graph_model=Inject('viewer/graph_model'), graph=Inject('viewer/graph')):
  {% if expanded %}
    {% for name in expanded %}
    graph_model['{{name}}'].view.expand()
    {% endfor %}
  {% endif %}

  {% if selected %}
    graph.select(graph_mode['{{selected.model.name}}'].view)
  {% endif %}

  {% if (not selected) and (not expanded) %}
    pass
  {% endif %}

"""

save_file_epilog = """
expand()
"""

gtkwave_load_func_template = """

@reg_inject
def load_after_vcd_loaded(
        graph_model=Inject('viewer/graph_model'),
        gtkwave=Inject('viewer/gtkwave')):

    if any(not intf.loaded for intf in gtkwave.graph_intfs):
        return

{% for intf in intfs %}
{% for pipe in intf.pipes_on_wave %}
    gtkwave.show_pipe(graph_model["{{pipe.name}}"])
{% endfor %}
{% endfor %}


@inject_async
def gtkwave_load(gtkwave=Inject('viewer/gtkwave')):
    for i, intf in enumerate(gtkwave.graph_intfs):
        if intf.loaded:
            load_after_vcd_loaded()
        else:
            intf.vcd_loaded.connect(load_after_vcd_loaded)

"""

layout_load_func_tempalte = """

@inject_async
def layout_load(layout=Inject('viewer/layout')):
    win = layout.current_layout
    win.setDirection({{top_direction}})
    win.child(0).remove()

{{commands|indent(4,True)}}

    list(layout.windows())[0].activate()

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
def save_expanded(
        root=Inject('viewer/graph_model'), graph=Inject('viewer/graph')):
    expanded = list(GraphStatusSaver().visit(root))

    selected = graph.selected_items()
    if selected:
        selected = selected[0]

    return load_str_template(expand_func_template).render({
        'expanded':
        expanded,
        'selected':
        selected
    })


@reg_inject
def save_gtkwave(gtkwave=Inject('viewer/gtkwave')):
    return load_str_template(gtkwave_load_func_template).render({
        'intfs':
        gtkwave.graph_intfs
    })


def save_win_layout(name, layout):
    res = ''
    for i, child in enumerate(layout):
        if isinstance(child, Window):
            res += (f"{name}.addLayout(Window("
                    f"parent=None, buff=layout.get_buffer_by_name("
                    f"\"{child.buff.name}\")))\n")
        else:
            res += save_layout(child, name + str(i))
            res += f"{name}.addLayout({name + str(i)})\n"

    streches = [layout.stretch(i) for i in range(layout.count())]

    res += f"""
for i, s in enumerate({streches}):
    {name}.setStretch(i, s)
"""

    return res


@reg_inject
def save_layout(layout=Inject('viewer/layout')):
    return load_str_template(layout_load_func_tempalte).render({
        'commands':
        save_win_layout('win', layout.current_layout),
        'top_direction':
        str(layout.current_layout.direction()).partition('.')[2]
    })


def save():
    with open(get_save_file_path(), 'w') as f:
        f.write(save_file_prolog)

        f.write(save_expanded())

        f.write(save_gtkwave())

        f.write(save_layout())

        f.write(save_file_epilog)


@reg_inject
def get_save_file_path(outdir=MayInject('sim/artifact_dir')):
    return os.path.abspath(os.path.join(outdir, 'pygears_view_save.py'))
