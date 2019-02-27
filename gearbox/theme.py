from pygears.conf import PluginBase, config, reg_inject, Inject


@reg_inject
def themify(style, theme=Inject('gearbox/theme')):
    return style.format(**theme)


class ThemePlugin(PluginBase):
    @classmethod
    def bind(cls):
        config.define(
            'gearbox/theme/text_color', default='rgba(255, 255, 255, 150)')
