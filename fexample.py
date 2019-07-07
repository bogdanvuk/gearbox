from pygears.typing import Tuple, Uint
from pygears.sim.modules.drv import drv
from pygears.lib import rng
from pygears.lib import shred, filt

drv(t=Tuple[Uint[32], Uint[32], Uint[2]], seq=[(2, 1 << 14, 2)]) \
    | rng \
    | shred

    # | rng \
    # | shred
