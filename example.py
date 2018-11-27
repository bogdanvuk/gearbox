from pygears_view import main
from pygears.cookbook.rng import rng
from pygears.common import shred

# add(2, 3) | shred
# rng(8) | shred
# main()

from pygears.typing import Tuple, Uint
from pygears.cookbook.rng import rng
from pygears.sim.modules.verilator import SimVerilated

from pygears.cookbook.verif import verif
from pygears.sim import sim
from pygears.sim.modules.drv import drv

from pygears_view import PyGearsView
from pygears.sim.extens.vcd import VCD
from pygears import bind

seq = [(2, 8, 2)]
verif(
    drv(t=Tuple[Uint[4], Uint[4], Uint[2]], seq=seq),
    f=rng(sim_cls=SimVerilated),
    ref=rng(name='ref_model'))


bind('svgen/debug_intfs', ['*'])
sim(outdir='build', extens=[VCD, PyGearsView])
