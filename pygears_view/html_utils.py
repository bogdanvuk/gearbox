def tabulate(table, style=""):
    res = [f'<table {style}>']
    for row in table:
        res.append('<tr>')
        for style, elem in row:
            res.append(f'<td {style}>{elem}</td>')

        res.append('</tr>')

    res.append('</table>')

    return '\n'.join(res)


def fontify(s, color=None, bold=False):
    style = ''
    if color:
        style += f' color={color}'

    if bold:
        s = f'<b>{s}<\b>'

    return f'<font{style}>{s}</font>'
