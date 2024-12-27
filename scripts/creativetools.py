"""
Yet another building script. Some worldedit-like commands + custom features.

.. codeauthor:: Liza
"""

import colorsys, math, random
from piqueserver.commands import command
from pyspades.common import coordinates, make_color
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from pyspades.contained import BlockAction, SetColor
from twisted.internet.task import LoopingCall


MAX_UNDO = 20

colornames = { # colors from polm's worldedit script via Kuma's cfog.py
    'black': (0, 0, 0), 'white': (255, 255, 255), 'grey': (127, 127, 127), 'red': (255, 0, 0),
    'lime': (0, 255, 0), 'blue': (0, 0, 255), 'yellow': (255, 255, 0), 'magenta': (255, 0, 255),
    'cyan': (0, 255, 255), 'orange': (255, 165, 0), 'pink': (255, 130, 108), 'violet': (148, 0, 211),
    'purple': (155, 48, 255), 'indigo': (75, 0, 130), 'orchid': (218, 112, 214), 'lavender': (230, 230, 250),
    'navy': (0, 0, 127), 'peacock': (51, 161, 201), 'azure': (240, 255, 255), 'aqua': (0, 238, 238),
    'turquoise': (64, 224, 208), 'teal': (56, 142, 142), 'aquamarine': (127, 255, 212), 'emerald': (0, 201, 87),
    'sea': (84, 255, 159), 'cobalt': (61, 145, 64), 'mint': (189, 252, 201), 'palegreen': (152, 251, 152),
    'forest': (34, 139, 34), 'green': (0, 128, 0), 'grass': (124, 252, 0), 'chartreuse': (127, 255, 0),
    'olive': (142, 142, 56), 'ivory': (238, 238, 224), 'beige': (245, 245, 220), 'khaki': (240, 230, 140),
    'banana': (227, 207, 87), 'gold': (201, 137, 16), 'goldenrod': (218, 165, 32), 'lace': (253, 245, 230),
    'wheat': (245, 222, 179), 'moccasin': (255, 222, 173), 'papaya': (255, 239, 213), 'eggshell': (252, 230, 201),
    'tan': (210, 180, 140), 'brick': (178, 34, 34), 'skin': (255, 211, 155), 'melon': (227, 168, 105),
    'carrot': (237, 145, 33), 'peru': (205, 133, 63), 'linen': (250, 240, 230), 'peach': (238, 203, 173),
    'chocolate': (139, 69, 19), 'sienna': (160, 82, 45), 'coral': (255, 127, 80), 'sepia': (94, 38, 18),
    'salmon': (198, 113, 113), 'tomato': (205, 55, 0), 'snow': (255, 250, 250), 'brown': (165, 42, 42),
    'maroon': (128, 0, 0), 'beet': (142, 56, 142), 'gray': (91, 91, 91), 'crimson': (220, 20, 60),
    'dew': (240, 255, 240), 'dirt': (71, 48, 35), 'bronze': (150, 90, 56), 'wood': (193, 154, 107),
    'silver': (168, 168, 168), 'lava': (205, 53, 39), 'oakwood': (115, 81, 58), 'redwood': (165, 42, 42),
    'sand': (244, 164, 96), 'chestnut': (149, 69, 53), 'russet': (128, 70, 27), 'cream': (255, 253, 208),
    'sky': (135, 206, 235), 'water': (65, 105, 225), 'smoke': (245, 245, 245), 'classic': (128, 232, 255),
    'fog': (134, 226, 254), 'default': (69, 43, 30), 'player': (216, 164, 107), 'case': (56, 40, 28),
    'ground': (103, 64, 40), 'lemon': (255, 255, 127), 'rose': (255, 0, 127), 'fuchsia': (255, 0, 255)
}

def get_rgb(h):
    if h in colornames:
        return colornames[h]
    try:
        h = h.strip('#')
        if len(h) == 3:
            h = ''.join([x*2 for x in h])
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except:
        return h

def build(con, x, y, z, color=None):
    if con.on_block_build_attempt(x, y, z) == False:
        return False
    block_action = BlockAction()
    block_action.player_id = 33
    block_action.x = x
    block_action.y = y
    block_action.z = z
    if color:
        color = [255 if value > 255 else value for value in color]
        color = tuple([0 if value < 0 else value for value in color])
        if color != con.build_queue_color:
            con.build_queue_color = color
            set_color = SetColor()
            set_color.player_id = 33
            set_color.value = make_color(*color)
            con.protocol.broadcast_contained(set_color)
        block_action.value = BUILD_BLOCK
        con.protocol.map.set_point(x, y, z, color)
    else:
        block_action.value = DESTROY_BLOCK
        con.protocol.map.remove_point(x, y, z)
    con.protocol.broadcast_contained(block_action, save=True)

def queue(con, x, y, z, color=False, save_history=True):
    if ((x in range(512)) and (y in range(512)) and (z in range(64))):
        if save_history:
            con.undo[-1][1] += [(x, y, z, con.protocol.world.map.get_color(x, y, z))]

        if color != False:
            con.build_queue += [(x, y, z, color)]
        else:
            con.build_queue += [(x, y, z, con.protocol.world.map.get_color(x, y, z))]

def get_points(con):
    points = []
    con.sel_a = [x if x > 0 else 0 for x in con.sel_a]
    con.sel_a = [x if x < 511 else 511 for x in con.sel_a]
    if con.sel_a[2] > 63: con.sel_a[2] = 63
    con.sel_b = [x if x > 0 else 0 for x in con.sel_b]
    con.sel_b = [x if x < 511 else 511 for x in con.sel_b]
    if con.sel_b[2] > 63: con.sel_b[2] = 63

    c = list(zip(con.sel_a, con.sel_b))
    if con.sel_shape == 'ellipsoid':
        center = [(x+y)/2 for x, y in zip(con.sel_a, con.sel_b)]
        x1 = (max(c[0]) - min(c[0]) + 1) // 2
        y1 = (max(c[1]) - min(c[1]) + 1) // 2
        z1 = (max(c[2]) - min(c[2]) + 1) // 2
        if x1 == 0: x1 = 1
        if y1 == 0: y1 = 1
        if z1 == 0: z1 = 1
        for x in range(min(c[0]), max(c[0])+1):
            for y in range(min(c[1]), max(c[1])+1):
                for z in range(min(c[2]), max(c[2])+1):
                    value = (x - center[0]) ** 2 / x1**2 + (y - center[1]) ** 2 / y1**2 + (z - center[2]) ** 2 / z1**2
                    if value <= 1:
                        points += [(x, y, z)]
    elif con.sel_shape == 'cylinder':
        center = [(x+y)/2 for x, y in zip(con.sel_a, con.sel_b)]
        x1 = (max(c[0]) - min(c[0]) + 1) // 2
        y1 = (max(c[1]) - min(c[1]) + 1) // 2
        for x in range(min(c[0]), max(c[0])+1):
            for y in range(min(c[1]), max(c[1])+1):
                for z in range(min(c[2]), max(c[2])+1):
                    value = (x - center[0]) ** 2 / x1**2 + (y - center[1]) ** 2 / y1**2
                    if value <= 1:
                        points += [(x, y, z)]
    else:
        for x in range(min(c[0]), max(c[0])+1):
            for y in range(min(c[1]), max(c[1])+1):
                for z in range(min(c[2]), max(c[2])+1):
                    points += [(x, y, z)]
    return points

def get_direction(con, direction):
    if direction:
        dirs = {'n': (1, -1), 'e': (0, 1), 's': (1, 1), 'w': (0, -1), 'u': (2, -1), 'd': (2, 1)}
        i, sign = dirs[direction]
    else:
        ori = con.world_object.orientation
        ori = (ori.x, ori.y, ori.z)
        ori_abs = [abs(x) for x in ori]
        i = ori_abs.index(max(ori_abs))
        sign = int(ori[i]/abs(ori[i]))
    return i, sign

def add_undo_step(con):
    con.undo += [[(con.sel_a, con.sel_b), []]]
    if len(con.undo) > MAX_UNDO:
        con.undo = con.undo[-MAX_UNDO:]
    con.redo = []

def add_dither(color, dither):
    dither = random.choice(range(-int(dither), int(dither)+1))
    return tuple([min(max(int(value) + dither, 0), 255) for value in color])

@command('s', 'sel')
def sel(con, shape=None):
    """
    Select area
    /sel <selection shape: cuboid/[e]llipsoid/[c]ylinder>
    """
    if shape == None:
        if not con.sel_a:
            con.sel_shape = 'cuboid'
    elif shape in ('e', 'ellipsoid'):
        con.sel_shape = 'ellipsoid'
        con.send_chat('Selection shape changed')
        if con.sel_a:
            return
    elif shape in ('c', 'cyl', 'cylinder'):
        con.sel_shape = 'cylinder'
        con.send_chat('Selection shape changed')
        if con.sel_a:
            return
    else:
        con.sel_shape = 'cuboid'
        con.send_chat('Selection shape changed')
        if con.sel_a:
            return

    if con.selection:
        con.selection = False
        con.sel_a = None
        con.sel_b = None
        return 'Selection cancelled'
    else:
        con.selection = True
        con.sel_a = None
        con.sel_b = None
        return 'Selection started. Select two points by clicking on or placing corner blocks'

@command()
def unsel(con):
    """
    Remove selection
    /unsel
    """
    con.selection = False
    con.sel_a = None
    con.sel_b = None
    return 'Selection removed'

@command()
def expand(con, amount, direction=None):
    """
    Expand selection in given direction or in the direction player is looking at
    /expand <amount / [vert] (full height)> <[n]orth, [e]ast, [s]outh, [w]est, [u]p, [d]own>
    """
    if amount == 'vert':
        con.sel_a[2] = 0
        con.sel_b[2] = 63
        return 'Selection expanded'
    else:
        amount = int(amount)
    i, sign = get_direction(con, direction)
    if sign < 0:
        if con.sel_a[i] < con.sel_b[i]:
            con.sel_a[i] += amount*sign
        else:
            con.sel_b[i] += amount*sign
    else:
        if con.sel_a[i] > con.sel_b[i]:
            con.sel_a[i] += amount*sign
        else:
            con.sel_b[i] += amount*sign
    return 'Selection expanded'

@command()
def contract(con, amount, direction=None):
    """
    Contract selection in given direction or in the direction player is looking at
    /expand <amount> <[n]orth, [e]ast, [s]outh, [w]est, [u]p, [d]own>
    """
    amount = int(amount)
    i, sign = get_direction(con, direction)
    if sign < 0:
        if con.sel_a[i] < con.sel_b[i]:
            con.sel_a[i] -= amount*sign
        else:
            con.sel_b[i] -= amount*sign
    else:
        if con.sel_a[i] > con.sel_b[i]:
            con.sel_a[i] -= amount*sign
        else:
            con.sel_b[i] -= amount*sign
    return 'Selection contracted'

def selection(con, func, args):
    if con.sel_a and con.sel_b:
        con.selection = False
    else:
        con.selection = True
        con.sel_a = None
        con.sel_b = None
        con.send_chat('Selection started. Select two points by clicking on corner blocks')
        con.deferred = (func, args)
        return True

def replace(con, source, colors):
    if selection(con, replace, (source, colors)):
        return
    try:
        value = colors[-1]
        if type(value) == type(0.0):
            colors = colors[:-1]
        else:
            value = int(value)
            if value != 0:
                colors = colors[:-1]
    except:
        value = 0
    if not colors:
        colors = ('#%02X%02X%02X ' % con.color,)
    weights = [int(x.split('%')[0]) if '%' in x else 1 for x in colors]
    colors = [get_rgb(x.split('%')[1]) if '%' in x else get_rgb(x) for x in colors]
    add_undo_step(con)
    for x, y, z in get_points(con):
        block = con.protocol.world.map.get_color(x, y, z)
        if source == 'any' or source == block or (source == 'solid' and block) or (source == None and block == None):
            color = random.choices(colors, weights, k = 1)[0]
            if color == 'random':
                queue(con, x, y, z, random.choices(range(256), k=3))
            elif color in ('0', 'remove'):
                queue(con, x, y, z, None)
            elif color in ('pattern', 'clipboard'):
                if con.clipboard:
                    lx, ly, lz = [x + 1 for x in con.clipboard[-1][:3]]
                    color = con.clipboard[x % lx * ly * lz + y % ly * lz + z % lz][-1]
                    if color:
                        queue(con, x, y, z, add_dither(color, value))
                    else:
                        queue(con, x, y, z, None)
                else:
                    return 'Use /copy to create pattern first'
            elif color in ('H=', 'L=', 'S=', 'H+', 'L+', 'S+'):
                h, l, s = colorsys.rgb_to_hls(*[x/255 for x in block])
                if color == 'H=': h = value
                elif color == 'L=': l = value
                elif color == 'S=': s = value
                elif color == 'H+': h += value
                elif color == 'L+': l += value
                elif color == 'S+': s += value
                if h > 1: h -= 1
                elif h < 0: h += 1
                hls = [min(max(x, 0), 1) for x in (h, l, s)]
                queue(con, x, y, z, [int(x*255) for x in colorsys.hls_to_rgb(*hls)])
            elif color == 'crossprocess':
                r, g, b = block
                queue(con, x, y, z, (r, g, int(value)))
            elif color == 'noise':
                queue(con, x, y, z, add_dither(block, value))
            elif color in ('empty', 'keep'):
                queue(con, x, y, z)
            else:
                queue(con, x, y, z, add_dither(color, value))
        else:
            queue(con, x, y, z)
    con.build_queue_start()


@command('set')
def c_set(con, *colors):
    """
    Fill selection with blocks
    /set <#aaa/red (color names are supported)> <#bbb - colors will be mixed randomly> <5%#ccc - % is used to set ratio, in this case with three colors it'll be 1:1:5> <dither>
    """
    replace(con, 'any', colors)

@command('re', 'rep', 'replace')
def c_replace(con, *colors):
    """
    Replace player-held color in selection
    /replace <target colors (same syntax as /set)>
    """
    replace(con, con.color, colors)

@command()
def fill(con, *colors):
    """
    Replace empty space in selection
    /fill <target colors (same syntax as /set)>
    """
    replace(con, None, colors)

@command()
def repaint(con, *colors):
    """
    Replace all solid (non-empty) blocks in selection
    /repaint <target colors (same syntax as /set)>
    """
    replace(con, 'solid', colors)


@command()
def hue(con, value=0.0):
    """
    /hue <value>
    """
    h, l, s = colorsys.rgb_to_hls(*[x/255 for x in con.color])
    replace(con, 'solid', ('H=', h))

@command()
def hueshift(con, value=0.618):
    """
    /hueshift <value>
    """
    value = float(value)
    if abs(value) > 1: value /= 100
    replace(con, 'solid', ('H+', value))

@command()
def brightness(con, value=0.0):
    """
    /brightness <value>
    """
    value = float(value)
    if abs(value) > 1: value /= 100
    replace(con, 'solid', ('L=', value))

@command('lighten', 'brightness')
def lighten(con, value=0.2):
    """
    /lighten <value>
    """
    value = float(value)
    if value > 1: value /= 100
    replace(con, 'solid', ('L+', value))

@command()
def darken(con, value=0.2):
    """
    /darken <value>
    """
    value = float(value)
    if value > 1: value /= 100
    replace(con, 'solid', ('L+', -value))

@command()
def saturation(con, value=0.0):
    """
    /saturation <value>
    """
    value = float(value)
    if abs(value) > 1: value /= 100
    replace(con, 'solid', ('S=', value))

@command()
def saturate(con, value=0.2):
    """
    /saturate <value>
    """
    value = float(value)
    if value > 1: value /= 100
    replace(con, 'solid', ('S+', value))

@command()
def desaturate(con, value=0.2):
    """
    /desaturate <value>
    """
    value = float(value)
    if value > 1: value /= 100
    replace(con, 'solid', ('S+', -value))

@command()
def crossprocess(con, value=153):
    """
    /crossprocess <value>
    """
    replace(con, 'solid', ('crossprocess', float(value)))

@command()
def noise(con, value=3):
    """
    /noise <value>
    """
    replace(con, 'solid', ('noise', float(value)))


@command('shift', 'mov')
def shift(con, count, direction=None, skip=False):
    """
    Move blocks in selection in given direction or in the direction player is looking at
    /shift <count> <[n]orth, [e]ast, [s]outh, [w]est, [u]p, [d]own> <skip empty space>
    """
    if selection(con, shift, (count, direction)):
        return
    count = int(count)
    i, sign = get_direction(con, direction)
    add_undo_step(con)
    buffer = []
    for x, y, z in get_points(con):
        buffer += [[x, y, z, con.protocol.world.map.get_color(x, y, z)]]
        queue(con, x, y, z, None)
    for point in buffer:
        point[i] += count*sign
        x, y, z, color = point
        if skip:
            if color:
                queue(con, x, y, z, color)
            else:
                queue(con, x, y, z)
        else:
            queue(con, x, y, z, color)
    ax, ay, az, color = buffer[0]
    con.sel_a = [ax, ay, az]
    bx, by, bz, color = buffer[-1]
    con.sel_b = [bx, by, bz]
    con.build_queue_start()

@command()
def stack(con, count, direction=None):
    """
    Repeat selection in given direction or in the direction player is looking at
    /stack <count> <[n]orth, [e]ast, [s]outh, [w]est, [u]p, [d]own>
    """
    if selection(con, stack, (count, direction)):
        return
    count = int(count)
    i, sign = get_direction(con, direction)
    add_undo_step(con)
    buffer = []
    for x, y, z in get_points(con):
        buffer += [[x, y, z, con.protocol.world.map.get_color(x, y, z)]]
    sizes = [max(x, y) - min(x, y) + 1 for x, y in zip(con.sel_a, con.sel_b)]
    for j in range(count):
        for point in buffer:
            point[i] += sizes[i]*sign
            queue(con, *point)
    con.build_queue_start()

@command()
def copy(con):
    """
    Save selection to clipboard
    /copy
    """
    if selection(con, copy, ()):
        return
    con.clipboard = []
    dx, dy, dz = [min(x, y) for x, y in zip(con.sel_a, con.sel_b)]
    for x, y, z in get_points(con):
        con.clipboard += [[x-dx, y-dy, z-dz, con.protocol.world.map.get_color(x, y, z)]]
    return 'Selection copied'

@command()
def cut(con):
    """
    Save selection to clipboard and remove selected blocks
    /cut
    """
    if selection(con, cut, ()):
        return
    add_undo_step(con)
    dx, dy, dz = [min(x, y) for x, y in zip(con.sel_a, con.sel_b)]
    for x, y, z in get_points(con):
        con.clipboard += [[x-dx, y-dy, z-dz, con.protocol.world.map.get_color(x, y, z)]]
        queue(con, x, y, z, None)
    con.build_queue_start()

@command()
def paste(con, skip=False):
    """
    Build blocks saved to clipboard
    /paste <skip empty space>
    """
    if not con.clipboard:
        return 'Use /copy or /cut to save selection first'
    add_undo_step(con)
    px, py, pz = con.get_location()
    dz = con.clipboard[-1][2]
    for p in con.clipboard:
        x, y, z, color = p
        x += int(px) + 1
        y += int(py) + 1
        z += int(pz) + 2 - dz
        if skip:
            if color:
                queue(con, x, y, z, color)
            else:
                queue(con, x, y, z)
        else:
            queue(con, x, y, z, color)
    x, y, z, color = con.clipboard[0]
    con.sel_a = [x + int(px) + 1, y + int(py) + 1, z + int(pz) + 2 - dz]
    x, y, z, color = con.clipboard[-1]
    con.sel_b = [x + int(px) + 1, y + int(py) + 1, z + int(pz) + 2 - dz]
    con.build_queue_start()

@command()
def rotate(con, rz=1, ry=0, rx=0):
    """
    Rotate selection n times per axis
    /rotate <z> <y> <x>
    """
    if selection(con, rotate, (rz, ry, rx)):
        return
    add_undo_step(con)
    buffer = []
    c = list(zip(con.sel_a, con.sel_b))
    lx, ly, lz = [max(x) - min(x) for x in zip(con.sel_a, con.sel_b)]
    dx, dy, dz = [min(x, y) for x, y in zip(con.sel_a, con.sel_b)]
    for x, y, z in get_points(con):
        buffer += [[x-dx, y-dy, z-dz, con.protocol.world.map.get_color(x, y, z)]]
        queue(con, x, y, z, None)

    for i in range(int(rz)):
        rot_buffer = []
        d = round((lx - ly) / 2)
        for point in buffer:
            x, y, z, color = point
            rot_buffer += [(ly-y+d, x-d, z, color)]
        buffer = rot_buffer.copy()

    for i in range(int(ry)):
        rot_buffer = []
        d = round((lz - lx) / 2)
        for point in buffer:
            x, y, z, color = point
            rot_buffer += [(z-d, y, lx-x+d, color)]
        buffer = rot_buffer.copy()

    for i in range(int(rx)):
        rot_buffer = []
        d = round((ly - lz) / 2)
        for point in buffer:
            x, y, z, color = point
            rot_buffer += [(x, lz-z+d, y-d, color)]
        buffer = rot_buffer.copy()

    for point in buffer:
        x, y, z, color = point
        queue(con, int(x)+dx, int(y)+dy, int(z)+dz, color)
    ax, ay, az, color = rot_buffer[0]
    con.sel_a = [ax+dx, ay+dy, az+dz]
    bx, by, bz, color = rot_buffer[-1]
    con.sel_b = [bx+dx, by+dy, bz+dz]
    con.build_queue_start()

@command()
def flip(con, plane):
    """
    Mirror selection across the plane
    /rotate <[n]orth, [s]outh, [e]ast, [w]est, [u]p, [d]own> (directions are for convenience, there are only 3 possible planes)
    """
    if selection(con, flip, plane):
        return
    add_undo_step(con)
    buffer = []
    c = list(zip(con.sel_a, con.sel_b))
    lx, ly, lz = [max(x) - min(x) for x in zip(con.sel_a, con.sel_b)]
    dx, dy, dz = [min(x, y) for x, y in zip(con.sel_a, con.sel_b)]
    for x, y, z in get_points(con):
        buffer += [[x-dx, y-dy, z-dz, con.protocol.world.map.get_color(x, y, z)]]
        queue(con, x, y, z, None)
    rot_buffer = []
    for point in buffer:
        x, y, z, color = point
        if plane in ('e', 'w'):
            rot_buffer += [(lx-x, y, z, color)]
        elif plane in ('n', 's'):
            rot_buffer += [(x, ly-y, z, color)]
        elif plane in ('u', 'd'):
            rot_buffer += [(x, y, lz-z, color)]
    buffer = rot_buffer.copy()
    for point in buffer:
        x, y, z, color = point
        queue(con, int(x)+dx, int(y)+dy, int(z)+dz, color)
    con.build_queue_start()

@command()
def brush(con, radius=None, mode='set', *colors):
    """
    Toggle brush mode
    /brush <radius> <set/replace/fill/repaint>
    """
    con.brush_mode = mode
    con.brush_colors = colors
    if radius:
        radius = int(radius)
        if radius > 32:
            radius = 32
        elif radius < 1:
            radius = 1
    if con.brush:
        if radius:
            con.brush_size = radius
            return 'Brush size changed'
        else:
            con.brush = False
            con.sel_shape = 'cuboid'
            return 'Brush disabled'
    else:
        if radius:
            con.brush_size = radius
        con.brush = True
        return 'Brush enabled'

def brush_build(con, x, y, z, action):
    con.sel_a = (x + con.brush_size, y + con.brush_size, z + con.brush_size)
    con.sel_b = (x - con.brush_size, y - con.brush_size, z - con.brush_size)
    con.sel_shape = 'ellipsoid'

    if action == 'build':
        if con.brush_mode == 'set':
            replace(con, 'any', con.brush_colors)
        elif con.brush_mode == 'replace':
            replace(con, con.color, con.brush_colors)
        elif con.brush_mode == 'fill':
            replace(con, None, con.brush_colors)
        elif con.brush_mode == 'repaint':
            replace(con, 'solid', con.brush_colors)
    elif action == 'destroy':
        replace(con, 'any', ('remove',))

@command()
def center(con):
    """
    Mark center of selection with blocks
    /center
    """
    if selection(con, center, ()):
        return
    add_undo_step(con)
    x, y, z = [sum(x)/2 for x in zip(con.sel_a, con.sel_b)]
    for x1 in range(int(x), math.ceil(x)+1):
        for y1 in range(int(y), math.ceil(y)+1):
            for z1 in range(int(z), math.ceil(z)+1):
                queue(con, x1, y1, z1, con.color)
    con.build_queue_start()


def random_repeat(length, colors, ratio):
    array = [random.choice(range(colors))]
    i = 1
    while i < length:
        action = random.random() > ratio
        if action:
            n = i & (~(i - 1))
            array += array[-n:]
            i += n
        else:
            array += [random.choice(range(colors))]
            i += 1
    return array

@command('randomrepeat', 'rr')
def randomrepeat(con, colors='2%#444,2%#555,2%#343,2%#554,2%#565,2%#455,2%#465,#C92', ratio_empty=1, randomness=0.5, dither=0):
    """
    /randomrepeat <colors> <emptiness> <randomness> <dither>
    """
    if selection(con, randomrepeat, (colors, ratio_empty, randomness, dither)):
        return
    add_undo_step(con)
    weights = [int(x.split('%')[0]) if '%' in x else 1 for x in colors.split(',')]
    weights += [round(sum(weights) * float(ratio_empty))]
    colors = [get_rgb(x.split('%')[1]) if '%' in x else get_rgb(x) for x in colors.split(',')]
    colors += [None]
    colors = [[x] * y for x, y in zip(colors, weights)]
    colors = [x for y in colors for x in y]
    n = 64
    volume = random_repeat(n**3, len(colors), float(randomness))
    for x, y, z in get_points(con):
        color = colors[volume[(x % n) * n**2 + (y % n) * n + z]]
        if color:
            queue(con, x, y, z, add_dither(color, int(dither)), False)
        else:
            queue(con, x, y, z, None, False)
    con.build_queue_start()

@command()
def forestgen(con, sector, dither=3):
    """
    /forestgen
    """
##    if selection(con, randomrepeat, (colors, ratio_empty, randomness, dither)):
##        return
    add_undo_step(con)
    a = [x**0.5 for x in [0, 1, 2, 4, 5, 8, 9, 10, 13, 16, 17]]
    b = [(x-0.5)**0.5 for x in [1, 3, 5, 7, 9, 13, 15, 19, 21, 23, 25]]
    treetypes = [
        (a, (0,0),(0,0),(1,1),(2,1),(2,1),(2,1),(1,1),(1,1),(1,1),(0,1),(0,1)), # cypress
        (a, (0,0),(3,1),(4,1),(3,1),(1,1),(3,1),(1,1),(0,1),(1,1),(0,1),(0,1)), # spruce
        (a, (1,0),(4,1),(7,1),(4,1),(3,1),(4,1),(3,1),(1,1),(3,1),(1,1),(0,1),(1,1),(0,1),(0,1)), # big spruce
        (b, (1,0),(0,0),(3,1),(4,1),(4,1),(3,1),(1,1)),
        (b, (1,0),(0,0),(4,1),(3,1),(4,1),(3,1),(1,1)),
        (b, (1,0),(0,0),(0,0),(1,1),(3,1),(4,1),(3,1),(4,1),(3,1),(1,1)),
        ]
    treetypes += [(a, (1,1),(0,1))] * len(treetypes) # shrub
##    treetypes += [
##        (b, (0,2),(0,2),(1,3),(0,3)), # mushroom
##        (a, (0,2),(0,2),(1,4),(0,4)), # red mushroom
##        ]

    for i in range(128):
        tree = random.choice(treetypes)
        x1 = random.choice(range(4, 60)) - (tree[0] == b) * 0.5
        y1 = random.choice(range(4, 60)) - (tree[0] == b) * 0.5
        trunk = random.choice(range(119, 134)), random.choice(range(68, 85)), random.choice(range(68, 85))
        leaves = random.choice(range(34, 68)), random.choice(range(85, 153)), random.choice(range(68, 85))
        mushroom1 = random.choice(range(204, 255)), random.choice(range(187, 204)), random.choice(range(134, 187))
        mushroom2 = random.choice(range(187, 221)), random.choice(range(119, 153)), random.choice(range(85, 102))
        mushroom3 = random.choice(range(187, 204)), random.choice(range(51, 68)), random.choice(range(51, 68))
        colors = (trunk, leaves, mushroom1, mushroom2, mushroom3)
        for z in range(1, len(tree)):
            for y in range(0, 64):
                for x in range(0, 64):
                    d, clr = tree[z]
                    if ((x-x1)**2+(y-y1)**2)**0.5 <= tree[0][d]:
                        sx, sy = coordinates(sector)
                        queue(con, sx+x, sy+y, 62-z, add_dither(colors[clr], int(dither)))
    con.build_queue_start()

@command()
def undo(con, steps=1):
    """
    Undo previous commands
    /undo <steps>
    """
    if not con.undo:
        return 'No actions to undo'
    for step in range(int(steps)):
        con.redo += [[con.undo[-1][0], []]]
        con.sel_a, con.sel_b = con.undo[-1][0]
        for p in con.undo[-1][1]:
            x, y, z, color = p
            con.redo[-1][1] += [(x, y, z, con.protocol.world.map.get_color(x, y, z))]
            con.build_queue += [(x, y, z, color)]
        con.undo = con.undo[:-1]
    con.build_queue_start()

@command()
def redo(con, steps=1):
    """
    Redo previously undone commands
    /redo <steps>
    """
    if not con.redo:
        return 'No actions to redo'
    for step in range(int(steps)):
        con.undo += [[con.redo[-1][0], []]]
        con.sel_a, con.sel_b = con.redo[-1][0]
        for p in con.redo[-1][1]:
            x, y, z, color = p
            con.undo[-1][1] += [(x, y, z, con.protocol.world.map.get_color(x, y, z))]
            con.build_queue += [(x, y, z, color)]
        con.redo = con.redo[:-1]
    con.build_queue_start()


def apply_script(protocol, connection, config):
    class CTConnection(connection):

        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.selection = False
            self.sel_a = None
            self.sel_b = None
            self.sel_shape = 'cuboid'
            self.build_queue_loop = None
            self.build_queue = []
            self.build_queue_len = None
            self.build_queue_color = None
            self.undo = []
            self.redo = []
            self.deferred = None
            self.brush = False
            self.brush_size = 1
            self.brush_mode = 'set'
            self.clipboard = []

        def on_shoot_set(self, state):
            if state == True:
                if self.brush:
                    if not self.build_queue:
                        coords = self.world_object.cast_ray(64)
                        if coords:
                            brush_build(self, *list(coords), 'build')
                if self.selection:
                    coords = self.world_object.cast_ray(32)
                    if coords:
                        if self.sel_a:
                            self.sel_b = list(coords)
                            self.send_chat('Selection created')
                            if self.deferred:
                                func, args = self.deferred
                                func(self, *args)
                                self.deferred = None
                        else:
                            self.sel_a = list(coords)
                            self.send_chat('First corner has been selected')
            connection.on_shoot_set(self, state)

        def on_secondary_fire_set(self, state):
            if state == True:
                if self.brush:
                    coords = self.world_object.cast_ray(64)
                    if coords:
                        brush_build(self, *list(coords), 'destroy')
                if self.selection:
                    coords = self.world_object.cast_ray(32)
                    if coords:
                        self.sel_a = list(coords)
                        self.send_chat('First corner has been redefined')
            connection.on_secondary_fire_set(self, state)

        def on_block_destroy(self, x, y, z, value):
            if self.selection:
                if self.sel_a:
                    self.sel_b = [x, y, z]
                    self.send_chat('Selection created')
                    if self.deferred:
                        func, args = self.deferred
                        func(self, *args)
                        self.deferred = None
                else:
                    self.sel_a = [x, y, z]
                    self.send_chat('First corner has been selected')
                return False
            if connection.on_block_destroy(self, x, y, z, value) == False:
                return False

        def on_block_build_attempt(self, x, y, z):
            if self.selection:
                if self.sel_a:
                    self.sel_b = [x, y, z]
                    self.send_chat('Selection created')
                    if self.deferred:
                        func, args = self.deferred
                        func(self, *args)
                        self.deferred = None
                else:
                    self.sel_a = [x, y, z]
                    self.send_chat('First corner has been selected')
                return False
            if connection.on_block_build_attempt(self, x, y, z) == False:
                return False

        def build_queue_start(self):
            self.build_queue_len = len(self.build_queue)
##            self.build_queue = sorted(self.build_queue, key=lambda x: (x[3] is not None, x[3])) # blocks queued for removal should be processed first
            self.build_queue = iter(self.build_queue)
            self.build_queue_loop = LoopingCall(self.build_queue_batch)
            self.build_queue_loop.start(0.01)

        def build_queue_batch(self):
            for i in range(180):
                try:
                    block = next(self.build_queue)
                    if block:
                        if build(self, *block) == False:
                            self.build_queue_loop.stop()
                            self.build_queue = []
                            if not self.brush:
                                self.send_chat('%s block(s) have been changed' % self.build_queue_len)
                            break
                except StopIteration:
                    self.build_queue_loop.stop()
                    self.build_queue = []
                    if not self.brush:
                        self.send_chat('%s block(s) have been changed' % self.build_queue_len)
                    break

    return protocol, CTConnection
