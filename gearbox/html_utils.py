import pygments
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name

from .theme import themify


def tabulate(table, style=""):
    res = [f'<table {style}>']
    for row in table:
        res.append('<tr>')
        for style, elem in row:
            res.append(f'<td {style}>{elem}</td>')

        res.append('</tr>')

    res.append('</table>')

    return '\n'.join(res)


def fontify(s, bold=False, **style):
    style = ';'.join(
        [f'{k.replace("_", "-")}:{themify(v)}' for k, v in style.items()])

    if style:
        style_expr = f' style="{style}"'
    else:
        style_expr = ''

    if bold:
        s = f'<b>{s}</b>'

    res = f'<span{style_expr}>{s}</span>'
    return res


def highlight(text, language, style='emacs', add_style=True):
    lexer = get_lexer_by_name(language)
    html = pygments.highlight(text, lexer, HtmlFormatter(style=style))

    if add_style:
        return highlight_style(html)
    else:
        return html


def highlight_style(text):
    return '\n'.join(("<style>", HtmlFormatter().get_style_defs('.highlight'),
                      '.highlight  { background: rgba(255, 255, 255, 0); }'
                      "</style>", text))
