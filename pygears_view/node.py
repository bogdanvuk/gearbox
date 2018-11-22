from NodeGraphQt.widgets.node_abstract import AbstractNodeItem


class NodeItem(AbstractNodeItem):
    def __init__(self, model, parent=None):
        super(NodeItem, self).__init__(model.basename, parent)
