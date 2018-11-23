from pygears_view import main
from pygears.cookbook.rng import rng
from pygears.common import shred

rng(8) | shred
main()
