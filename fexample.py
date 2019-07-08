from functools import partial
from pygears import gear, alternative
from pygears.sim.modules import SimVerilated
from pygears.typing import Tuple, Uint
from pygears.sim.modules.drv import drv
from pygears.lib import rng
from pygears.lib import shred, filt, quenvelope, directed


@gear
def test(din):
    print("Try1")
    return din | filt


@gear
def deeper(din):
    return din | quenvelope(lvl=2)


@alternative(test)
@gear
def test_alt(din):
    print("Try2")
    return din | deeper


seq = [(2, 1 << 4, 2), (2, 1 << 10, 2)]
# ref = [list(range(*seq[0]))]
ref = [[2, 3]]

directed(
    drv(t=Tuple[Uint[32], Uint[32], Uint[2]], seq=seq),
    f=rng(sim_cls=SimVerilated),
    ref=ref)

# drv(t=Tuple[Uint[32], Uint[32], Uint[2]], seq=[(2, 1 << 10, 2)]) \
#     | rng \
#     | test \
#     | shred

# | quenvelope(lvl=2) \
# | rng \
# | shred
