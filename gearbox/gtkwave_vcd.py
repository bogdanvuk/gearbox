from .node_model import find_cosim_modules, PipeModel, NodeModel
from pygears import reg, find
from pygears.hdl import hdlgen
from pygears.conf import inject, Inject
from pygears.core.graph import PathError
from pygears.typing import Tuple, Union, Queue, Array, typeof
from .timekeep import timestep


def get_item_signals(subgraph, signals, prefix=''):
    item_signals = {}
    item = subgraph
    item_path = []
    lp = len(prefix)

    def find_child(parent, name):
        # Try name as submodule
        if name in parent:
            return parent[name]

        # Try name as interface name
        intf_name = p.rpartition('_')[0]

        if intf_name in parent:
            return parent[intf_name]

        return None

    for name in signals:
        if prefix and not name.startswith(prefix):
            continue

        if prefix:
            name = name[lp:]

        item = subgraph
        path = name.split('.')

        new_item_path = []

        import itertools
        # for p, prev_item in itertools.zip_longest(path[1:], item_path):
        for p, prev_item in itertools.zip_longest(path, item_path):
            if prev_item and p == prev_item.basename:
                item = prev_item
            else:
                child_item = find_child(item, p)
                if child_item is None:
                    break

                item = child_item

            new_item_path.append(item)

            if not item.hierarchical:
                break

        item_path = new_item_path

        if item not in item_signals:
            item_signals[item] = []

        item_signals[item].append(name)

    return item_signals


class VCDMap:
    def __init__(self, module, sigs):
        self.module = module
        self.model = reg['gearbox/graph_model_map'][module]
        self.sigs = sigs
        self.sigmap = get_item_signals(find('/'), sigs, self.path_prefix)
        self.item_signals = {}

    @property
    @inject
    def subgraph(self, graph=Inject('gearbox/graph_model')):
        if self.module.parent is None:
            return graph

        return graph[self.module.name[1:]]

    @property
    def vcd_pipes(self):
        for item in self.item_signals:
            if isinstance(item, PipeModel):
                yield item

    @property
    def name(self):
        return self.module.name

    @property
    def timestep(self):
        ts = timestep()
        if ts is None:
            return 0

        return ts

    def __contains__(self, item):
        try:
            self[item]
            return True
        except KeyError:
            return False


class VerilatorVCDMap(VCDMap):
    def __init__(self, module, sigs):
        self.hdlgen_map = reg[f'hdlgen/map']

        self.hdlmod = self.hdlgen_map[module]
        if self.hdlmod.wrapped:
            self.path_prefix = '.'.join(['TOP', self.hdlmod.wrap_module_name, ''])
        else:
            self.path_prefix = 'TOP.'

        super().__init__(module, sigs)

    def pipe_data_signal_stem(self, item):
        basename = self.item_basename(item)
        if f'{self.path_prefix}{basename}' == "TOP.top_v_wrap.top.dout":
            breakpoint()

        return f'{self.path_prefix}{basename}_data'

    def pipe_handshake_signals(self, item):
        basename = self.item_basename(item)
        return (f'{self.path_prefix}{basename}_valid', f'{self.path_prefix}{basename}_ready')

    def item_basename(self, item):
        parent = item.rtl.parent
        path = [item.basename]
        while parent != self.module.parent:
            path.append(self.hdlgen_map[parent].inst_name)
            parent = parent.parent

        return '.'.join(reversed(path))

    def get_pipe_groups(self, item):
        sigs = self[item]
        return get_type_groups(sigs, item.rtl.dtype, [self.pipe_data_signal_stem(item)])

    def __getitem__(self, item):
        if item not in self.item_signals:
            if isinstance(item, PipeModel):
                if not item.svintf:
                    raise KeyError

                parent_node = item.rtl.parent

                basename = self.item_basename(item)
                sigs = [
                    f'{self.path_prefix}{s}' for s in self.sigmap[parent_node]
                    if s.startswith(basename)
                ]
                self.item_signals[item] = sigs
            else:
                self.item_signals[item] = [f'{self.path_prefix}{s}' for s in self.sigmap[item.rtl]]

        return self.item_signals[item]

    def __contains__(self, item):
        if isinstance(item, PipeModel):
            if not item.svintf:
                return False

            rtl = item.parent.rtl
        else:
            rtl = item.rtl

        return self.module.has_descendent(rtl)


def get_type_groups(sigs, t, path):
    if not typeof(t, (Tuple, Union, Queue, Array)):
        name = '.'.join(path)
        sel = []
        for s in sigs:
            if s.startswith(name) and (len(s) == len(name) or s[len(name)] == '['):
                sel.append(s)

        return sel

    group = {}
    for name in t.fields:
        group[name] = get_type_groups(sigs, t[name], path + [name])

    return group


class PyGearsVCDMap(VCDMap):
    def __init__(self, module, sigs):
        self.path_prefix = ''
        super().__init__(module, sigs)

    def pipe_data_signal_stem(self, item):
        return self.item_basename(item) + '.data'

    def pipe_handshake_signals(self, item):
        return (self.item_basename(item) + '.valid', self.item_basename(item) + '.ready')

    def pipe_source_port(self, item):
        return item.rtl.end_producer[0].consumers[0]

    def item_basename(self, item):
        prod_port = item.rtl.consumers[item.consumer_id]
        item_name_stem = prod_port.name[1:]
        return item_name_stem.replace('/', '.')

    def get_pipe_groups(self, item):
        sigs = self[item]
        return get_type_groups(sigs, item.rtl.dtype, [self.item_basename(item), 'data'])

    def __getitem__(self, item):
        if item.rtl in reg[f'hdlgen/map']:
            raise KeyError

        if item not in self.item_signals:
            if isinstance(item, PipeModel):
                prod_port = item.rtl.consumers[item.consumer_id]
                prod_gear = prod_port.gear

                if prod_gear not in self.sigmap:
                    raise KeyError

                basename = self.item_basename(item)
                sigs = []
                for s in self.sigmap[prod_gear]:
                    if s.startswith(basename) and s[len(basename)] == '.':
                        sigs.append(s)

                self.item_signals[item] = sigs
            else:
                raise KeyError

        return self.item_signals[item]

    def __contains__(self, item):
        return item.rtl not in reg[f'hdlgen/map']
