from gearbox import main
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

from gearbox import Gearbox
from pygears.sim.extens.vcd import VCD
from pygears import bind

from pygears.typing_common.pprint import pprint

# pprint.pprint(Tuple[Uint[8], Uint[8]], width=30)

# pprint.pprint(
#     Tuple[{
#         'test1': Tuple[{
#             'test1': Tuple[Uint[1], Uint[2]],
#             'test2': Uint[8]
#         }],
#         'test2': Uint[8]
#     }],
#     indent=4,
#     width=22,
#     compact=True)

# pprint.pprint({
#     'test1': {
#         'test1': Uint[8],
#         'test2': Uint[8]
#     },
#     'test2': Uint[8]
# },
#               indent=4,
#               width=20,
#               compact=True)

# pprint.pprint({
#     'test1': {
#         'test1': Uint[8],
#         'test2': Uint[8]
#     },
#     'test2': Uint[8]
# },
#               width=10)

seq = [(2, 1 << 22, 2)]
verif(
    drv(t=Tuple[Uint[32], Uint[32], Uint[2]], seq=seq),
    f=rng(sim_cls=SimVerilated),
    ref=rng(name='ref_model'))

# from pygears.cookbook.verif import directed
# from pygears.common.rom import rom

# data = list(range(2000))
# addr = list(range(2000))

# directed(
#     drv(t=Uint[16], seq=addr),
#     f=rom(sim_cls=SimVerilated, data=data, dtype=Uint[16]),
#     ref=data)

import os
os.system("cd /tools/gtkwave/_install/gtkwave-gtk3-3.3.98/src; make install")

# bind('svgen/debug_intfs', ['/rng/cfg'])
bind('svgen/debug_intfs', ['*'])
# sim(outdir='build', extens=[VCD])
sim(outdir='build',
    check_activity=True,
    extens=[partial(Gearbox, live=True, reload=True)])
