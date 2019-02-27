import os

from pygears.conf import Inject, PluginBase, config, reg_inject


def themify(style):
    @reg_inject
    def stylerepl(match, theme=Inject('gearbox/theme')):
        return theme[match.group(1)]

    import re
    return re.sub(r'@([\w-]+)', stylerepl, style)


class ThemePlugin(PluginBase):
    @classmethod
    def bind(cls):
        config.define(
            'gearbox/theme/text-color', default='rgba(150, 150, 150, 255)')

        config.define(
            'gearbox/theme/text-color-comment', default='#2a937c')

        config.define(
            'gearbox/theme/text-color-keyword', default='#ff79c6')

        config.define(
            'gearbox/theme/text-color-object-name', default='#ba6ec3')

        config.define(
            'gearbox/theme/text-color-string', default='#2d8b6e')

        # config.define(
        #     'gearbox/theme/background-color', default='rgba(41, 43, 46, 255)')
        config.define(
            'gearbox/theme/background-color', default='#ff292b2e')
