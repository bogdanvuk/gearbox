import runpy
import os
from pygears.conf import Inject, reg_inject, MayInject, config
from .graph import GraphVisitor
from jinja2 import Environment, BaseLoader
from pygears.core.hier_node import HierYielderBase
from .layout import Window

save_file_prolog = """
from pygears.conf import Inject, config, inject_async, reg_inject
from gearbox.utils import single_shot_connect
from gearbox.layout import Window
from gearbox.description import describe_file
from PySide2 import QtWidgets
from functools import partial
"""

expand_func_template = """

@reg_inject
def expand(buff, graph_model=Inject('gearbox/graph_model')):
  {% if expanded %}
    {% for name in expanded %}
    graph_model['{{name}}'].view.expand()
    {% endfor %}
  {% endif %}

  {% if selected %}
    buff.view.select(graph_model['{{selected.model.name}}'].view)
  {% endif %}

  {% if (not selected) and (not expanded) %}
    pass
  {% endif %}

"""

gtkwave_load_func_template = """

@reg_inject
def load_after_vcd_loaded(
        buff,
        graph_model=Inject('gearbox/graph_model'),
        gtkwave=Inject('gearbox/gtkwave/inst')):

{% for buff in buffers %}
    if buff.name == "{{buff.name}}":
    {% for item in buff.intf.items_on_wave %}
        gtkwave.show_item(graph_model["{{item.name}}"])
    {% endfor %}
{% endfor %}


def gtkwave_load(buff):
    if buff.intf.loaded:
        load_after_vcd_loaded(buff)
    else:
        single_shot_connect(buff.intf.vcd_loaded,
                            partial(load_after_vcd_loaded, buff))

"""

layout_load_func_template = """

@reg_inject
def place_buffer(buff, window, layout=Inject('gearbox/layout')):
    layout.windows[window].place_buffer(buff)

buffer_init_commands = {
{% for k,v in buffer_init_commands.items() -%}
  {% if v %}
    '{{k}}': [{{v|join(', ')}}],
  {% endif %}
{% endfor %}
}


@reg_inject
def buffer_initializer(buff, layout=Inject('gearbox/layout')):
    if buff.name in buffer_init_commands:
        for f in buffer_init_commands[buff.name]:
            f(buff)

        del [buffer_init_commands[buff.name]]
        if not buffer_init_commands:
            layout.new_buffer.disconnect(buffer_initializer)


@inject_async
def layout_load(layout=Inject('gearbox/layout')):
    layout.clear_layout()
    layout.buffers.clear()
    win = layout.current_layout
    win.setDirection({{top_direction}})
    win.child(0).remove()

{{commands|indent(4,True)}}

    layout.windows[0].activate()

    layout.new_buffer.connect(buffer_initializer)

    descriptions_load()

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
def save_expanded(buffer_init_commands,
                  root=Inject('gearbox/graph_model'),
                  graph=Inject('gearbox/graph')):
    expanded = list(GraphStatusSaver().visit(root))

    selected = graph.selected_items()
    if selected:
        selected = selected[0]

    buffer_init_commands['graph'].append('expand')

    return load_str_template(expand_func_template).render({
        'expanded':
        expanded,
        'selected':
        selected
    })


@reg_inject
def save_gtkwave(buffer_init_commands, layout=Inject('gearbox/layout')):
    buffers = [
        buff for buff in layout.buffers
        if buff.domain == "gtkwave" and buff.intf.items_on_wave
    ]
    for b in buffers:
        buffer_init_commands[b.name].append('gtkwave_load')

    if buffers:
        return load_str_template(gtkwave_load_func_template).render({
            'buffers':
            buffers
        })

    return ''


description_load_template = """

@reg_inject
def descriptions_load(layout=Inject('gearbox/layout')):
{% if commands %}
{{commands|indent(4,True)}}
{% else %}
    pass
{% endif %}

"""


@reg_inject
def save_description(buffer_init_commands, layout=Inject('gearbox/layout')):
    buffers = [buff for buff in layout.buffers if buff.domain == "description"]
    res = ''
    for b in buffers:
        if hasattr(b.view, 'fn'):
            res += f'describe_file("{b.view.fn}", lineno={b.view.lineno})\n'

    return load_str_template(description_load_template).render({
        'commands':
        res
    })


def save_win_layout(name, layout):
    res = ''
    for i, child in enumerate(layout):
        if isinstance(child, Window):
            res += (f"{name}.addLayout(Window(" f"parent=None))\n")
        else:
            res += save_layout(child, name + str(i))
            res += f"{name}.addLayout({name + str(i)})\n"

    streches = [layout.stretch(i) for i in range(layout.count())]

    res += f"""
for i, s in enumerate({streches}):
    {name}.setStretch(i, s)
"""

    return res


save_configuration_template = """
{% for k,v in configs.items() -%}
config['{{k}}'] = {{v}}
{% endfor %}
"""


def save_configuration():
    changed = {
        name: var.val
        for name, var in config.definitions.items() if var.changed
    }

    return load_str_template(save_configuration_template).render({
        'configs':
        changed
    })


@reg_inject
def save_layout(buffer_init_commands, layout=Inject('gearbox/layout')):

    for i, w in enumerate(layout.windows):
        if w.buff:
            buffer_init_commands[w.buff.name].append(
                f'partial(place_buffer, window={i})')

    return load_str_template(layout_load_func_template).render({
        'buffer_init_commands':
        buffer_init_commands,
        'layout':
        layout,
        'commands':
        save_win_layout('win', layout.current_layout),
        'top_direction':
        str(layout.current_layout.direction()).partition('.')[2]
    })


def load():
    try:
        runpy.run_path(get_save_file_path())
    except Exception as e:
        print(f'Loading save file failed: {e}')


@reg_inject
def save(layout=Inject('gearbox/layout')):
    with open(get_save_file_path(), 'w') as f:
        buffer_init_commands = {b.name: [] for b in layout.buffers}

        f.write(save_file_prolog)

        f.write(save_configuration())

        f.write(save_expanded(buffer_init_commands))

        f.write(save_gtkwave(buffer_init_commands))

        f.write(save_description(buffer_init_commands))

        f.write(save_layout(buffer_init_commands))


@reg_inject
def get_save_file_path(
        outdir=MayInject('sim/artifact_dir'),
        script_fn=Inject('gearbox/model_script_name')):

    if script_fn is None:
        script_fn = '.gearbox.py'
    else:
        stem = os.path.splitext(os.path.basename(script_fn))[0]
        script_fn = f'.{stem}_save.py'

    return os.path.abspath(os.path.join(outdir, script_fn))
