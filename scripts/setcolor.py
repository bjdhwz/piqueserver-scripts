"""
Set current block color

Commands
^^^^^^^^

* ``/setcolor <r> <g> <b>`` set color using RGB values
* ``/setcolor <#aabbcc>`` set color using hex representation
* ``/setcolor <#abc>`` set color using short hex representation
* ``/setcolor`` set to random color
* ``/setcolor ?`` get current color

.. codeauthor:: Liza
"""

import colorsys
from random import choices
from piqueserver.commands import command
from pyspades.common import make_color
from pyspades.contained import SetColor

colornames = {
    # custom colors go here

    # Game colors
    'default': (135, 206, 235), # Piqueserver default sky
    'sky': (134, 226, 254), # OS rendition of default sky
    'classic': (128, 232, 255), # 'Classic' sky
    'dirt': (103, 64, 40), # OS dirt
    'ground': (71, 48, 35), # Voxlap dirt
    'case': (56, 40, 28), 'player': (216, 164, 107),

    # Used for color mixing, e.g. "darkred"
    'dark': (0, 0, 0), 'light': (255, 255, 255), 'pale': (127, 127, 127),
}

def rgb2lin(rgb):
    lin = []
    for a in rgb:
        if a <= 0.04045:
            b = a / 12.92
        else:
            b = ((a + 0.055) / 1.055) ** 2.4
        lin += [b]
    return lin

def lin2rgb(lin):
    rgb = []
    for a in lin:
        if a <= 0.0031308:
            b = a * 12.92
        else:
            b = 1.055 * (a ** (1.0 / 2.4)) - 0.055
        rgb += [int(b)]
    return rgb

def getrgb(h):
    if h in colornames:
        return colornames[h]
    else:
        h = h.strip('#')
        if len(h) == 3:
            h = ''.join([x*2 for x in h])
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


@command('c', 'clr', 'setcolor', 'color')
def setcolor(connection, *args):
    """
    Set current block color
    /clr <name>, /clr <r> <g> <b>, /clr <#aabbcc>, /clr <#abc>, no arguments to get random color or /clr ? to get current color
    """
    try:
        if len(args) == 3:
            rgb = [min(int(x.strip(',')), 255) for x in args]

        elif len(args) == 2:
            h = ''.join(args).lower().replace('grey', 'gray')
            if h in colornames:
                rgb = colornames[h]
            else:
                clr_a, clr_b = args
                if clr_a.lower() in colornames and clr_b.lower() in colornames:
                    rgb = [sum(x) // 2 for x in zip(colornames[clr_a], colornames[clr_b])]

        elif len(args) == 1:
            h = args[0].lower().replace('grey', 'gray')
            if h == '?':
                colorname = ''
                if connection.color in colornames.values():
                    i = list(colornames.values()).index(connection.color)
                    colorname = ' [%s]' % list(colornames.keys())[i].capitalize()
                return '#%02X%02X%02X ' % connection.color + str(connection.color) + colorname
            rgb = None
            if h in colornames:
                rgb = colornames[h]
            else:
                for clr_a in colornames:
                    if clr_a in h:
                        clr_b = [x for x in h.split(clr_a) if x][0]
                        if clr_b in colornames:
                            rgb = [sum(x) // 2 for x in zip(colornames[clr_a], colornames[clr_b])]
                            break
                if not rgb:
                    for name in colornames:
                        if h in name:
                            rgb = colornames[name]
                            break
                if not rgb:
                    if '+' in h:
                        rgb = [sum(x) // len(x) for x in zip(*[getrgb(color) for color in h.split('+')])]
                    elif '-' in h:
                        rgb = lin2rgb([sum(x) / len(x) for x in zip(*[rgb2lin(getrgb(color)) for color in h.split('-')])])
                    elif '*' in h:
                        rgb = [int(y * 255) for y in colorsys.hls_to_rgb(*[sum(x) / len(x) for x in zip(*[colorsys.rgb_to_hls(*[channel/255 for channel in getrgb(color)]) for color in h.split('*')])])]
                    else:
                        rgb = getrgb(h)

        elif len(args) == 0:
            rgb = choices(range(256), k=3)

        set_color = SetColor()
        set_color.value = make_color(*rgb)
        set_color.player_id = connection.player_id
        connection.protocol.broadcast_contained(set_color)
        connection.color = tuple(rgb)

    except:
        raise ValueError


def apply_script(protocol, connection, config):
    return protocol, connection
