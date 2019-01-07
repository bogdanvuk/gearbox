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
    style = ';'.join([f'{k.replace("_", "-")}:{v}' for k, v in style.items()])

    if style:
        style_expr = f' style="{style}"'
    else:
        style_expr = ''

    if bold:
        s = f'<b>{s}</b>'

    res = f'<span{style_expr}>{s}</span>'
    print(f'Fontify: {res}')

    return res
