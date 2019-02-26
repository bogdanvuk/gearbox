from pygears.typing import Tuple, Uint
from pygears.sim.modules.drv import drv
from pygears.cookbook import rng
from pygears.common import shred, filt

drv(t=Tuple[Uint[32], Uint[32], Uint[2]], seq=[(2, 1 << 14, 2)]) \
    | rng \
    | filt \
    | shred
