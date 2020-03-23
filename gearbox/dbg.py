from functools import wraps
from pygears.conf import PluginBase, reg


def dbg_connect(signal, f):
    signal.connect(debuggable(f))


class Debug():
    def __init__(self):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type:
            import traceback
            import pdb
            import sys
            extype, value, tb = sys.exc_info()
            traceback.print_exc()
            pdb.post_mortem(tb)


def debuggable(f):
    @wraps(f)
    def wrap(*args, **kwds):
        try:
            if reg['gearbox/dbg/print_entrance']:
                print(f'Entering {f}')

            res = f(*args, **kwds)

            if reg['gearbox/dbg/print_entrance']:
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

    if reg['gearbox/dbg/except']:
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
        reg.confdef('gearbox/dbg/except', default=True)
        reg.confdef('gearbox/dbg/print_entrance', default=False)
