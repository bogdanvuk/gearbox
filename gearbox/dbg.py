from functools import wraps
from pygears.conf import PluginBase, config


def dbg_connect(signal, f):
    signal.connect(debuggable(f))


def debuggable(f):
    @wraps(f)
    def wrap(*args, **kwds):
        try:
            if config['gearbox/dbg/print_entrance']:
                print(f'Entering {f}')

            res = f(*args, **kwds)

            if config['gearbox/dbg/print_entrance']:
                print(f'Leaving {f}')

            return res
        except Exception as e:
            import traceback
            import pdb
            import sys
            extype, value, tb = sys.exc_info()
            traceback.print_exc()
            pdb.post_mortem(tb)
            raise e

    if config['gearbox/dbg/except']:
        return wrap
    else:
        return f


class Profiler():
    def __init__(self, profile=True):
        self.profile = profile
        if self.profile:
            import cProfile
            self.pr = cProfile.Profile()

    def __enter__(self):
        if self.profile:
            self.pr.enable()

    def __exit__(self, exc_type, exc_value, tb):
        if self.profile:
            self.pr.disable()

            import pstats, io
            s = io.StringIO()
            sortby = pstats.SortKey.CUMULATIVE
            ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
            ps.print_stats()
            print(s.getvalue())

        if exc_type:
            import traceback
            import pdb
            traceback.print_exc()
            pdb.post_mortem(tb)


class ThemePlugin(PluginBase):
    @classmethod
    def bind(cls):
        config.define('gearbox/dbg/except', default=True)
        config.define('gearbox/dbg/print_entrance', default=False)
