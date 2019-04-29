import os

from pygears.conf import Inject, PluginBase, config, inject


def themify(style):
    @inject
    def stylerepl(match, theme=Inject('gearbox/theme')):
        return theme[match.group(1)]

    import re
    return re.sub(r'@([\w-]+)', stylerepl, style)


class ThemePlugin(PluginBase):
    @classmethod
    def bind(cls):
        config.define('gearbox/theme/text-color', default='#b0b0b0')
        config.define('gearbox/theme/text-color-comment', default='#2a937c')
        config.define('gearbox/theme/text-color-keyword', default='#4d97d5')
        config.define('gearbox/theme/text-color-constant', default='#d060ff')
        config.define(
            'gearbox/theme/text-color-object-name', default='#ba6ec3')
        config.define('gearbox/theme/text-color-class-name', default='#ba6ec3')
        config.define('gearbox/theme/text-color-string', default='#2d8b6e')
        config.define('gearbox/theme/text-color-error', default='#e02020')
        config.define('gearbox/theme/background-color', default='#292b2e')
        config.define('gearbox/theme/border-color', default='#a0a0a0')
