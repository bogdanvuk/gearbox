from pygears_view import main
from pygears.cookbook.rng import rng
from pygears.common import shred

from functools import partial

# import pygraphviz as pgv

# d = {
#     '1': {
#         '2': None,
#         '3': None
#     },
#     '2': {
#         '1': None,
#         '3': None
#     },
#     '3': {
#         '2': None
#     },
#     '4': {
#         '6': None,
#         '5': None
#     },
#     '5': {
#         '1': None
#     },
#     '6': {
#         '3': None
#     }

# }
# G = pgv.AGraph(d, directed=True)
# G.graph_attr['rankdir'] = 'LR'
# G.get_node(1).attr['width'] = 2
# G.get_node(1).attr['height'] = 2
# G.layout(prog='dot')
# for n in G.nodes_iter():
#     print({k: v for k, v in n.attr.items()})

# for n in G.edges_iter():
#     print({k: v for k, v in n.attr.items()})

# G.draw('proba.png')

from pygears.typing import Tuple, Uint
from pygears.cookbook.rng import rng
from pygears.sim.modules.verilator import SimVerilated

from pygears.cookbook.verif import verif
from pygears.sim import sim
from pygears.sim.modules.drv import drv

from pygears_view import PyGearsView
from pygears.sim.extens.vcd import VCD
from pygears import bind

seq = [(2, 1 << 16, 2)]
verif(
    drv(t=Tuple[Uint[20], Uint[20], Uint[2]], seq=seq),
    f=rng(sim_cls=SimVerilated),
    ref=rng(name='ref_model'))

bind('svgen/debug_intfs', ['*'])
# sim(outdir='build', extens=[VCD])
sim(outdir='build',
    check_activity=True,
    extens=[VCD, partial(PyGearsView, live=True, reload=True)])
