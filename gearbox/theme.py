import os

from pygears.conf import Inject, PluginBase, reg, inject


def themify(style):
    @inject
    def stylerepl(match, theme=Inject('gearbox/theme')):
        return theme[match.group(1)]

    import re
    return re.sub(r'@([\w-]+)', stylerepl, style)


class ThemePlugin(PluginBase):
    @classmethod
    def bind(cls):
        reg.confdef('gearbox/theme/text-color', default='#b0b0b0')
        reg.confdef('gearbox/theme/text-color-comment', default='#2a937c')
        reg.confdef('gearbox/theme/text-color-keyword', default='#4d97d5')
        reg.confdef('gearbox/theme/text-color-constant', default='#d060ff')
        reg.confdef(
            'gearbox/theme/text-color-object-name', default='#ba6ec3')
        reg.confdef('gearbox/theme/text-color-class-name', default='#ba6ec3')
        reg.confdef('gearbox/theme/text-color-string', default='#2d8b6e')
        reg.confdef('gearbox/theme/text-color-error', default='#e02020')
        reg.confdef('gearbox/theme/background-color', default='#292b2e')
        reg.confdef('gearbox/theme/border-color', default='#a0a0a0')
