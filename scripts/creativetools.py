"""
Yet another building script. Some worldedit-like commands + custom features.

.. codeauthor:: Liza
"""

import colorsys, hashlib, math, random
from itertools import accumulate
from piqueserver.commands import command
from pyspades import contained as loaders
from pyspades import world
from pyspades.common import coordinates, make_color
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from pyspades.contained import BlockAction, SetColor
from twisted.internet.reactor import callLater
from twisted.internet.task import LoopingCall


MAX_UNDO = 50

FN_ENABLED = True # Warning: /fn uses eval() function which allows any player with access to it execute ANY CODE on server

SCIPY_ENABLED = True # Enable /rot to support rotations other than by 90 degrees and /scale commands which require scipy

if SCIPY_ENABLED:
    try:
        from scipy.ndimage import gaussian_filter, zoom, rotate as rot3d
    except:
        print("creativetools.py: /rot and /scale commands disabled, because SciPy package is not found. Do 'pip install scipy', or set SCIPY_ENABLED to False.")

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

def get_rgb(h, con=None):
    if h in ('H=', 'L=', 'S=', 'H+', 'L+', 'S+'):
        return h
    h = h.strip().lower().replace('grey', 'gray')
    if h in colornames:
        return colornames[h]
    if h == 'light_effect':
        return light
    if 'pattern' in h:
        return h
    for clr_a in colornames:
        if clr_a in h:
            clr_b = [x for x in h.split(clr_a) if x][0]
            if clr_b in colornames:
                return [sum(x) // 2 for x in zip(colornames[clr_a], colornames[clr_b])]
    for name in colornames:
        if h in name:
            return colornames[name]
    try:
        if h == '*':
            return tuple(random.choices(range(256), k=3))

        # Gradients
        # Linear RGB
        elif '->' in h:
            clr_a, clr_b = [
                     rgb2lin(get_rgb(color)) if color
                else rgb2lin(get_rgb('#%02X%02X%02X' % con.color))
                for color in h.split('->')
                ]
            def get_gradient(con, x, y, z):
                ax, ay, az = con.sel_a
                bx, by, bz = con.sel_b
                dist_a = ((x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2) ** 0.5
                dist_b = ((x - bx) ** 2 + (y - by) ** 2 + (z - bz) ** 2) ** 0.5
                dist = dist_a / (dist_a + dist_b)
                return tuple(lin2rgb([a * (1 - dist) + b * dist for a, b in zip(clr_a, clr_b)]))
            return get_gradient
        # HLS
        elif '=>' in h:
            clr_a, clr_b = [
                     colorsys.rgb_to_hls(*[channel/255 for channel in get_rgb(color)]) if color
                else colorsys.rgb_to_hls(*[channel/255 for channel in get_rgb('#%02X%02X%02X' % con.color)])
                for color in h.split('=>')
                ]
            def get_gradient(con, x, y, z):
                ax, ay, az = con.sel_a
                bx, by, bz = con.sel_b
                dist_a = ((x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2) ** 0.5
                dist_b = ((x - bx) ** 2 + (y - by) ** 2 + (z - bz) ** 2) ** 0.5
                dist = dist_a / (dist_a + dist_b)
                return tuple(int(x * 255) for x in colorsys.hls_to_rgb(*[a * (1 - dist) + b * dist for a, b in zip(clr_a, clr_b)]))
            return get_gradient
        # RGB
        elif '>' in h:
            clr_a, clr_b = [
                     get_rgb(color) if color
                else get_rgb('#%02X%02X%02X' % con.color)
                for color in h.split('>')
                ]
            def get_gradient(con, x, y, z):
                ax, ay, az = con.sel_a
                bx, by, bz = con.sel_b
                dist_a = ((x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2) ** 0.5
                dist_b = ((x - bx) ** 2 + (y - by) ** 2 + (z - bz) ** 2) ** 0.5
                dist = dist_a / (dist_a + dist_b)
                return tuple(int(a * (1 - dist) + b * dist) for a, b in zip(clr_a, clr_b))
            return get_gradient

        # Mixed (solid color produced out of input colors)
        # RGB
        elif '+' in h:
            return tuple([
                sum(x) // len(x) for x in zip(*[
                         get_rgb(color) if color
                    else get_rgb('#%02X%02X%02X' % con.color)
                    for color in h.split('+')])
                ])
        # Linear RGB
        elif '-' in h:
            return tuple(lin2rgb([
                sum(x) / len(x) for x in zip(*[
                         rgb2lin(get_rgb(color)) if color
                    else rgb2lin(get_rgb('#%02X%02X%02X' % con.color))
                    for color in h.split('-')])])
                )
        # HLS
        elif '*' in h.lower():
            return tuple([
                int(y * 255) for y in colorsys.hls_to_rgb(*[sum(x) / len(x) for x in zip(*[
                         colorsys.rgb_to_hls(*[channel/255 for channel in get_rgb(color)]) if color
                    else colorsys.rgb_to_hls(*[channel/255 for channel in get_rgb('#%02X%02X%02X' % con.color)])
                    for color in h.split('*')])])
                ])

        # Ranges (random color picked from input range)
        # RGB
        elif ':' in h:
            clr_a, clr_b = [
                     get_rgb(color) if color
                else get_rgb('#%02X%02X%02X' % con.color)
                for color in h.split(':')
                ]
            def get_mixed(*args):
                rnd = random.random()
                return tuple(int(a * rnd + b * (1 - rnd)) for a, b in zip(clr_a, clr_b))
            return get_mixed
        # Linear RGB
        elif '=' in h:
            clr_a, clr_b = [
                     rgb2lin(get_rgb(color)) if color
                else rgb2lin(get_rgb('#%02X%02X%02X' % con.color))
                for color in h.split('=')
                ]
            def get_mixed(*args):
                rnd = random.random()
                return tuple(lin2rgb([a * rnd + b * (1 - rnd) for a, b in zip(clr_a, clr_b)]))
            return get_mixed
        # HLS
        elif '^' in h:
            clr_a, clr_b = [
                     colorsys.rgb_to_hls(*[channel/255 for channel in get_rgb(color)]) if color
                else colorsys.rgb_to_hls(*[channel/255 for channel in get_rgb('#%02X%02X%02X' % con.color)])
                for color in h.split('~')
                ]
            def get_mixed(*args):
                rnd = random.random()
                return tuple(int(x * 255) for x in colorsys.hls_to_rgb(*[a * rnd + b * (1 - rnd) for a, b in zip(clr_a, clr_b)]))
            return get_mixed

        else:
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
    block_action.player_id = 34 + con.player_id % 12
    block_action.x = x
    block_action.y = y
    block_action.z = z
    if color:
        color = tuple([min(max(int(value), 0), 255) for value in color])
        if color != con.protocol.world.map.get_color(x, y, z):
##            if color != con.build_queue_color:
##                con.build_queue_color = color
            set_color = SetColor()
            set_color.player_id = 34 + con.player_id % 12
            set_color.value = make_color(*color)
            con.protocol.broadcast_contained(set_color)

            block_action.value = BUILD_BLOCK
            con.protocol.map.set_point(x, y, z, color)
            con.protocol.broadcast_contained(block_action, save=True)
    else:
        if con.protocol.world.map.get_color(x, y, z):
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
    con.sel_a = [max(0, min(x, 511)) for x in con.sel_a]
    con.sel_a[2] = min(con.sel_a[2], 63)
    con.sel_b = [max(0, min(x, 511)) for x in con.sel_b]
    con.sel_b[2] = min(con.sel_b[2], 63)
    highlight_selection(con)

    c = list(zip(con.sel_a, con.sel_b))
    if con.sel_shape in ('ellipsoid', 'near'):
        center = [(x+y)/2 for x, y in c]
        x1 = max(1, (max(c[0]) - min(c[0]) + 1) / 2)
        y1 = max(1, (max(c[1]) - min(c[1]) + 1) / 2)
        z1 = max(1, (max(c[2]) - min(c[2]) + 1) / 2)
        for x in range(min(c[0]), max(c[0])+1):
            for y in range(min(c[1]), max(c[1])+1):
                for z in range(min(c[2]), max(c[2])+1):
                    value = (x - center[0]) ** 2 / x1**2 + (y - center[1]) ** 2 / y1**2 + (z - center[2]) ** 2 / z1**2
                    if value <= 1:
                        points += [(x, y, z)]
    elif con.sel_shape == 'cylinder':
        center = [(x+y)/2 for x, y in c]
        x1 = max(1, (max(c[0]) - min(c[0]) + 1) / 2)
        y1 = max(1, (max(c[1]) - min(c[1]) + 1) / 2)
        for x in range(min(c[0]), max(c[0])+1):
            for y in range(min(c[1]), max(c[1])+1):
                for z in range(min(c[2]), max(c[2])+1):
                    value = (x - center[0]) ** 2 / x1**2 + (y - center[1]) ** 2 / y1**2
                    if value <= 1:
                        points += [(x, y, z)]
    elif con.sel_shape == 'line':
        points = world.cube_line(*(con.sel_a + con.sel_b))
        for _ in range(16):
            last_point = list(points[-1])
            if last_point != con.sel_b:
                points += world.cube_line(*(last_point + con.sel_b))
            else:
                break
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
    try:
        return tuple([min(max(int(value) + dither, 0), 255) for value in color])
    except:
        return (0, 0, 0)

def add_tempblock(con, x, y, z, color):
    con.highlighted_blocks += [(x, y, z)]
    block_action = BlockAction()
    block_action.player_id = 34
    block_action.x = x
    block_action.y = y
    block_action.z = z
    set_color = SetColor()
    set_color.player_id = 34
    set_color.value = make_color(*color)
    con.protocol.broadcast_contained(set_color)
    block_action.value = BUILD_BLOCK
    con.send_contained(block_action)

def remove_tempblock(con, x, y, z):
    block = con.protocol.world.map.get_color(x, y, z)
    if block:
        block_action = BlockAction()
        block_action.player_id = 34
        block_action.x = x
        block_action.y = y
        block_action.z = z
        set_color = SetColor()
        set_color.player_id = 34
        set_color.value = make_color(*block)
        con.protocol.broadcast_contained(set_color)
        block_action.value = BUILD_BLOCK
        con.send_contained(block_action)
    else:
        block_action = BlockAction()
        block_action.player_id = 34
        block_action.x = x
        block_action.y = y
        block_action.z = z
        block_action.value = DESTROY_BLOCK
        con.send_contained(block_action)

def highlight_selection(con, sector=False):
    for block in con.highlighted_blocks:
        remove_tempblock(con, *block)
    con.highlighted_blocks = []
    if con.beam:
        return
    if con.sel_a:
        add_tempblock(con, *con.sel_a, (255, 255, 0))
    if con.sel_b:
        add_tempblock(con, con.sel_b[0], con.sel_b[1], con.sel_a[2], (255, 255, 0))
        add_tempblock(con, con.sel_b[0], con.sel_a[1], con.sel_b[2], (255, 255, 0))
        add_tempblock(con, con.sel_b[0], con.sel_a[1], con.sel_a[2], (255, 255, 0))
        add_tempblock(con, con.sel_a[0], con.sel_b[1], con.sel_b[2], (255, 255, 0))
        add_tempblock(con, con.sel_a[0], con.sel_b[1], con.sel_a[2], (255, 255, 0))
        add_tempblock(con, con.sel_a[0], con.sel_a[1], con.sel_b[2], (255, 255, 0))
        add_tempblock(con, *con.sel_b, (255, 255, 0))
    if sector:
        for x, y in ((con.sel_a[0], con.sel_a[1]), (con.sel_a[0], con.sel_b[1]), (con.sel_b[0], con.sel_a[1]), (con.sel_b[0], con.sel_b[1]), ):
            for z in range(62):
                add_tempblock(con, x, y, z, (255, 255, 0))
    set_color = SetColor()
    set_color.player_id = 34
    set_color.value = make_color(*con.color)
    con.protocol.broadcast_contained(set_color)

@command('s', 'sel')
def sel(con, shape=None):
    """
    Select area
    /sel <selection shape: cuboid/[e]llipsoid/[c]ylinder/[A1-H8] sector>
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
    elif shape.upper() in [chr(x // 8 + ord('A')) + str(x % 8 + 1) for x in range(64)]:
        sector = shape.upper()
        x, y = coordinates(sector)
        con.sel_shape = 'cuboid'
        con.selection = False
        con.sel_a = [x, y, 0]
        con.sel_b = [x+63, y+63, 63]
        highlight_selection(con, sector=True)
        return 'Sector %s selected' % sector
    else:
        con.sel_shape = 'cuboid'
        con.send_chat('Selection shape changed')
        if con.sel_a:
            return

    if con.selection:
        con.selection = False
        con.sel_a = None
        con.sel_b = None
        highlight_selection(con)
        return 'Selection cancelled'
    else:
        con.selection = True
        con.sel_a = None
        con.sel_b = None
        highlight_selection(con)
        return 'Selection started. Select two points by clicking on or placing corner blocks'

@command('u', 'unsel')
def unsel(con):
    """
    Remove selection
    /unsel
    """
    con.selection = False
    con.sel_a = None
    con.sel_b = None
    highlight_selection(con)
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
        highlight_selection(con)
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
    highlight_selection(con)
    return 'Selection expanded [%sx%sx%s]' % tuple([max(x)-min(x)+1 for x in zip(con.sel_a, con.sel_b)])

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
    highlight_selection(con)
    return 'Selection contracted [%sx%sx%s]' % tuple([max(x)-min(x)+1 for x in zip(con.sel_a, con.sel_b)])

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

def hashint(s):
    sha2 = hashlib.sha256()
    sha2.update(bytes(s))
    return sha2.hexdigest()

def find_segment(segments, position):
    return next((i for i, c in enumerate(accumulate(segments)) if position % sum(segments) + 1 <= c))

def replace(con, source, colors, radius=None):
    if len(colors) == 3:
        try:
            colors = ['#%02X%02X%02X' % tuple(max(min(int(x), 255), 0) for x in colors)]
        except:
            pass
    if radius:
        radius = int(radius)
        if radius > 8 and not con.admin:
            radius = 8
        pos = con.world_object.position
        con.sel_a = (int(pos.x + radius), int(pos.y + radius), int(pos.z + radius + 3))
        con.sel_b = (int(pos.x - radius), int(pos.y - radius), int(pos.z - radius + 3))
        con.sel_shape = 'near'
        highlight_selection(con)
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
    colors = [get_rgb(x.split('%')[1], con) if '%' in x else get_rgb(x, con) for x in colors]
    add_undo_step(con)
    for x, y, z in get_points(con):
        block = con.protocol.world.map.get_color(x, y, z)
        if source == 'any' or source == block or (source == 'solid' and block) or (source == None and block == None):
            color = random.choices(colors, weights, k = 1)[0]

            if callable(color):
                color = color(con, x, y, z)

            if color == 'random':
                queue(con, x, y, z, random.choices(range(256), k=3))
            elif color in ('0', 'remove'):
                queue(con, x, y, z, None)
            elif color in ('empty', 'keep'):
                queue(con, x, y, z)
            elif color in ('cur', 'current'):
                queue(con, x, y, z, con.color)
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
            elif color == 'blend_rgb':
                r, g, b = block
                queue(con, x, y, z, tuple(int(
                    a * value + b * (1 - value))
                    for a, b in zip(con.color, block)))
            elif color == 'blend_linear':
                r, g, b = block
                queue(con, x, y, z, tuple(lin2rgb([
                    a * value + b * (1 - value)
                    for a, b in zip(rgb2lin(con.color), rgb2lin(block))])))
            elif color == 'blend_hls':
                r, g, b = block                
                queue(con, x, y, z, tuple(
                    int(x * 255) for x in colorsys.hls_to_rgb(*[a * value + b * (1 - value)
                    for a, b in zip(colorsys.rgb_to_hls(*[channel/255 for channel in con.color]), colorsys.rgb_to_hls(*[channel/255 for channel in block]))])))
            elif color == 'pattern_noise':
                queue(con, x, y, z, add_dither(block, value))
            elif color == 'pattern_brick':
                value = int(value)
                queue(con, x, y, z, tuple([min(max(int(v) + int(hashint((x+z%2) // 2 + ((y+z%2) // 2) * 512 + z * 64)[-3:], 16) % (value * 2) - value, 0), 255) for v in block]))
            elif color[:15] == 'pattern_checker':
                pattern = [[int(y) for y in list(x.split(':'))] * 2 for x in color[15:].split('x') if x]
                pattern += [[1, 1]]
                pattern = pattern * 3
                l, w, h = pattern[:3]
                if (find_segment(l, x) + find_segment(w, y) + find_segment(h, z)) % 2:
                    queue(con, x, y, z, tuple([min(max(int(v) + int(value), 0), 255) for v in block]))
                else:
                    queue(con, x, y, z, tuple([min(max(int(v) - int(value), 0), 255) for v in block]))
            elif color[:9] == 'patternx_':
                pattern = [[int(y) for y in list(x.split(':'))] * 2 for x in color[9:].split('x') if x]
                pattern += [[1, 1]]
                pattern = pattern * 3
                l, w, h = pattern[:3]
                value = int(value)
                queue(con, x, y, z, tuple([min(max(int(v) + int(hashint(find_segment(l, x) + find_segment(w, y) * 512 + find_segment(h, z) * 64)[-3:], 16) % (value * 2) - value, 0), 255) for v in block]))
            else:
                queue(con, x, y, z, add_dither(color, value))

        else:
            queue(con, x, y, z)
    con.build_queue_start()
    if con.sel_shape in ('line', 'near'):
        con.sel_shape = 'cuboid'


@command('set')
def c_set(con, *colors):
    """
    Fill selection with blocks
    /set <#aaa/red (color names are supported)> <#bbb - colors will be mixed randomly> <5%#ccc - % is used to set ratio, in this case with three colors it'll be 1:1:5> <dither>
    """
    replace(con, 'any', colors)

@command()
def setnear(con, radius, *colors):
    """
    Fill a radius around your position with blocks
    /set <radius> <#aaa/red (color names are supported)> <#bbb - colors will be mixed randomly> <5%#ccc - % is used to set ratio, in this case with three colors it'll be 1:1:5> <dither>
    """
    replace(con, 'any', colors, radius)

@command('re', 'rep', 'replace')
def c_replace(con, *colors):
    """
    Replace player-held color in selection
    /replace <target colors (same syntax as /set)>
    """
    replace(con, con.color, colors)

@command()
def replacenear(con, radius, *colors):
    """
    Replace player-held color in a radius around your position
    /replacenear <radius> <target colors (same syntax as /set)>
    """
    replace(con, con.color, colors, radius)

@command()
def fill(con, *colors):
    """
    Replace empty space in selection
    /fill <target colors (same syntax as /set)>
    """
    replace(con, None, colors)

@command()
def fillnear(con, radius, *colors):
    """
    Replace empty space in a radius around your position
    /fill <radius> <target colors (same syntax as /set)>
    """
    replace(con, None, colors, radius)

@command()
def repaint(con, *colors):
    """
    Replace all solid (non-empty) blocks in selection
    /repaint <target colors (same syntax as /set)>
    """
    replace(con, 'solid', colors)

@command()
def repaintnear(con, radius, *colors):
    """
    Replace all solid (non-empty) blocks in a radius around your position
    /repaint <radius> <target colors (same syntax as /set)>
    """
    replace(con, 'solid', colors, radius)


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
def blend(con, value=0.5, method=':'):
    """
    /blend <value>
    """
    value = float(value)
    if value > 1: value /= 100
    if method in ('rgb', ':'):
        replace(con, 'solid', ('blend_rgb', float(value)))
    elif method in ('linear', '='):
        replace(con, 'solid', ('blend_linear', float(value)))
    if method in ('hls', '~'):
        replace(con, 'solid', ('blend_hls', float(value)))

@command()
def noise(con, value=3, pattern='noise'):
    """
    /noise <value> <pattern> - possible patterns: brick, LxW (eg 2x3), LxWxH
    """
    if pattern in ('noise', 'brick'):
        replace(con, 'solid', ('pattern_' + pattern, float(value)))
    elif 'x' in pattern:
        replace(con, 'solid', ('patternx_' + pattern, float(value)))

@command()
def checker(con, value=3, pattern='2x2x2'):
    """
    /checker <value> <pattern> - possible patterns: LxW (eg 2x3), LxWxH, L:LxW:W (eg 2:1x3:4) etc
    """
    replace(con, 'solid', ('pattern_checker' + pattern, float(value)))

##@command()
##def grid(con, parts=3):
##    """
##    /grid <parts> <add walls> - possible patterns: LxW (eg 2x3), LxWxH, L:LxW:W (eg 2:1x3:4) etc
##    """
##    parts = int(parts)
##    l = max(con.sel_a[0], con.sel_b[0]) - min(con.sel_a[0], con.sel_b[0]) + 1
##    dividersLen = parts - 1
##    minPartLen = (l - dividersLen) // parts
##    left = minPartLen * parts + dividersLen
##    if selection(con, grid, ()):
##        return
##    add_undo_step(con)

##    x, y, z = [sum(x)/2 for x in zip(con.sel_a, con.sel_b)]
##    for x1 in range(int(x), math.ceil(x)+1):
##        for y1 in range(int(y), math.ceil(y)+1):
##            for z1 in range(int(z), math.ceil(z)+1):
##                queue(con, x1, y1, z1, con.color)
##    pattern = [[int(y) for y in list(x.split(':'))] * 2 for x in pattern.split('x') if x]
##    pattern += [[1, 1]]
##    pattern = pattern * 3
##    l, w, h = pattern[:3]
##    if (find_segment(l, x) + find_segment(w, y) + find_segment(h, z)) % 2:
##        queue(con, x, y, z, con.color)
##    con.build_queue_start()

@command()
def line(con, *colors):
    """
    /line <target colors (same syntax as /set)>
    """
    if len(colors) == 3:
        try:
            colors = ['#%02X%02X%02X' % tuple(max(min(int(x), 255), 0) for x in colors)]
        except:
            pass
    con.sel_shape = 'line'
    replace(con, 'any', colors)


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
            queue(con, x, y, z, color)
    ax, ay, az, color = buffer[0]
    con.sel_a = [ax, ay, az]
    bx, by, bz, color = buffer[-1]
    con.sel_b = [bx, by, bz]
    highlight_selection(con)
    con.build_queue_start()

@command()
def stack(con, count, direction=None):
    """
    Repeat selection in given direction or in the direction player is looking at
    /stack <count 1-64> <[n]orth, [e]ast, [s]outh, [w]est, [u]p, [d]own>
    """
    if selection(con, stack, (count, direction)):
        return
    count = int(count)
    if count > 64:
        count = 64
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
    con.clipboard = []
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
    highlight_selection(con)
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
        buffer += [[x - dx, y - dy, z - dz, con.protocol.world.map.get_color(x, y, z)]]
        queue(con, x, y, z, None)

    for _ in range(int(rz)):
        d = round((lx - ly) / 2)
        buffer = [(ly - y + d, x - d, z, color) for x, y, z, color in buffer]

    for _ in range(int(ry)):
        d = round((lz - lx) / 2)
        buffer = [(z - d, y, lx - x + d, color) for x, y, z, color in buffer]

    for _ in range(int(rx)):
        d = round((ly - lz) / 2)
        buffer = [(x, lz - z + d, y - d, color) for x, y, z, color in buffer]

    for point in buffer:
        x, y, z, color = point
        queue(con, int(x) + dx, int(y) + dy, int(z) + dz, color)

    ax, ay, az, _ = buffer[0]
    con.sel_a = [ax + dx, ay + dy, az + dz]
    bx, by, bz, _ = buffer[-1]
    con.sel_b = [bx + dx, by + dy, bz + dz]

    highlight_selection(con)
    con.build_queue_start()

if SCIPY_ENABLED:
    def create_buffer(con, c, dx, dy, dz):
            buffer = [[[-1 for _ in range(max(c[0]) - min(c[0]) + 1)] for _ in range(max(c[1]) - min(c[1]) + 1)]
                   for _ in range(max(c[2]) - min(c[2]) + 1)]

            for z in range(min(c[2]), max(c[2]) + 1):
                for y in range(min(c[1]), max(c[1]) + 1):
                    for x in range(min(c[0]), max(c[0]) + 1):
                        rgb = con.protocol.world.map.get_color(x, y, z)
                        if rgb:
                            r, g, b = rgb
                            color = r << 16 | g << 8 | b
                            buffer[z - dz][y - dy][x - dx] = color
            return buffer

    @command()
    def rot(con, rz=90, ry=0, rx=0):
        """
        Rotate selection by N degrees per axis. Supports float values (eg 0.5 = 180°)
        /rotate <z> <y> <x>
        """
        if selection(con, rot, (rz, ry, rx)):
            return
        add_undo_step(con)

        c = list(zip(con.sel_a, con.sel_b))
        lx, ly, lz = [max(x) - min(x) for x in zip(con.sel_a, con.sel_b)]
        dx, dy, dz = [min(x, y) for x, y in zip(con.sel_a, con.sel_b)]

        buffer = create_buffer(con, c, dx, dy, dz)

        for x, y, z in get_points(con):
            queue(con, x, y, z, None)

        if rx:
            buffer = rot3d(buffer, float(rx), (0, 1), order=0, cval=-1)
        if ry:
            buffer = rot3d(buffer, float(ry), (0, 2), order=0, cval=-1)
        if rz:
            buffer = rot3d(buffer, float(rz), (1, 2), order=0, cval=-1)

        bz = len(buffer)
        by = len(buffer[0])
        bx = len(buffer[0][0])

        mx = 0
        my = 0
        for z in range(bz):
            for y in range(by):
                for x in range(bx):
                    color = buffer[z][y][x]
                    if color != -1:
                        color = ((color >> 16) & 255, (color >> 8) & 255, color & 255)
                        ax = dx + lx // 2 - bx // 2 + x + 1
                        ay = dy + ly // 2 - by // 2 + y + 1
                        queue(con, ax, ay, z + dz + lz - bz + 1, color)
                        mx = max(mx, ax)
                        my = max(my, ay)

        con.sel_a = [dx + lx // 2 - bx // 2 + 1, dy + ly // 2 - by // 2 + 1, dz + lz - bz + 1]
        con.sel_b = [mx, my, dz + lz]
        con.build_queue_start()

    @command()
    def scale(con, sz=2, sy=None, sx=None):
        """
        Scale selection by a factor N, supports scaling per axis
        /scale <z or all axes> [<y> <x>]
        """
        sz = float(sz)
        if not sy:
            sy = sz
        sy = float(sy)
        if not sx:
            sx = sz
        sx = float(sx)

        if selection(con, scale, (sz, sy, sx)):
            return
        add_undo_step(con)

        c = list(zip(con.sel_a, con.sel_b))
        lx, ly, lz = [max(x) - min(x) for x in zip(con.sel_a, con.sel_b)]
        dx, dy, dz = [min(x, y) for x, y in zip(con.sel_a, con.sel_b)]

        buffer = create_buffer(con, c, dx, dy, dz)

        for x, y, z in get_points(con):
            queue(con, x, y, z, None)

        buffer = zoom(buffer, (sz, sy, sx), order=0, cval=-1)

        bz = len(buffer)
        by = len(buffer[0])
        bx = len(buffer[0][0])

        mx = 0
        my = 0
        for z in range(bz):
            for y in range(by):
                for x in range(bx):
                    color = buffer[z][y][x]
                    if color != -1:
                        color = ((color >> 16) & 255, (color >> 8) & 255, color & 255)
                        ax = dx+lx//2-bx//2+x+1
                        ay = dy+ly//2-by//2+y+1
                        queue(con, ax, ay, z+dz+lz-bz+1, color)
                        if ax > mx:
                            mx = ax
                        if ay > my:
                            my = ay

        con.sel_a = [dx+lx//2-bx//2+1, dy+ly//2-by//2+1, dz+lz-bz+1]
        con.sel_b = [mx, my, dz+lz]
        con.build_queue_start()

    @command()
    def blur(con, s=1.0):
        """
        Blur selection
        /blur <strength>
        """
        s = float(s)

        if selection(con, blur, (s,)):
            return

        add_undo_step(con)
        c = list(zip(con.sel_a, con.sel_b))
        dx, dy, dz = [min(x, y) for x, y in zip(con.sel_a, con.sel_b)]
        buffer = []
        for z in range(min(c[2]), max(c[2])+1):
            buffer += [[]]
            for y in range(min(c[1]), max(c[1])+1):
                buffer[z-min(c[2])] += [[]]
                for x in range(min(c[0]), max(c[0])+1):
                    rgb = con.protocol.world.map.get_color(x, y, z)
                    if rgb:
                        buffer[z-dz][y-dy] += [rgb]
                    else:
                        buffer[z-dz][y-dy] += [(127, 127, 127)]

        buffer = gaussian_filter(buffer, (s, s, s, 0))

        for z in range(len(buffer)):
            for y in range(len(buffer[0])):
                for x in range(len(buffer[0][0])):
                    color = buffer[z][y][x]
                    queue(con, dx+x, dy+y, z+dz, tuple(color))

        con.build_queue_start()

@command()
def flip(con, plane):
    """
    Mirror selection across the plane
    /flip <x, y or z> ([n]orth, [s]outh, [e]ast, [w]est, [u]p, [d]own can also be used)
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
        if plane in ('e', 'w', 'x'):
            rot_buffer += [(lx-x, y, z, color)]
        elif plane in ('n', 's', 'y'):
            rot_buffer += [(x, ly-y, z, color)]
        elif plane in ('u', 'd', 'z'):
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
    /brush <radius 1-6> <set/replace/fill/repaint>
    """
    con.brush_mode = mode
    con.brush_colors = colors
    if radius:
        radius = int(radius)
        if 'light_' in mode:
            if radius > 8:
                if not con.admin:
                    radius = 8
            elif radius < 1:
                radius = 1
        else:
            if radius > 6:
                if not con.admin:
                    radius = 6
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
        else:
            if 'light_' in mode:
                con.brush_size = 4
        con.brush = True
        return 'Brush enabled'

def brush_build(con, x, y, z, action):
    con.sel_a = (x + con.brush_size, y + con.brush_size, z + con.brush_size)
    con.sel_b = (x - con.brush_size, y - con.brush_size, z - con.brush_size)
    con.sel_shape = 'ellipsoid'
    highlight_selection(con)

    con.brush_source = (x, y, z)

    if action == 'build':
        if con.brush_mode == 'set':
            replace(con, 'any', con.brush_colors)
        elif con.brush_mode == 'replace':
            replace(con, con.color, con.brush_colors)
        elif con.brush_mode == 'fill':
            replace(con, None, con.brush_colors)
        elif con.brush_mode == 'repaint':
            replace(con, 'solid', con.brush_colors)
        elif con.brush_mode in ('light_effect', 'light_shadow'):
            con.sel_shape = 'cuboid'
            replace(con, 'solid', ('light_effect',))
    elif action == 'destroy':
        replace(con, 'any', ('remove',))

def light(con, x, y, z):
    dx = con.brush_source[0] - x
    dy = con.brush_source[1] - y
    dz = con.brush_source[2] - z
    dist = (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5
    if dist < con.brush_size:
        dist /= con.brush_size

        if con.brush_mode == 'light_shadow':
            if dist:
                steps = max(abs(dx), abs(dy), abs(dz))
                x_inc = dx / steps
                y_inc = dy / steps
                z_inc = dz / steps
                x1 = x
                y1 = y
                z1 = z

                for _ in range(steps + 1):
                    xyz = (round(x1), round(y1), round(z1))
                    if xyz != (x, y, z) and xyz != con.brush_source:
                        if con.protocol.world.map.get_color(*xyz):
                            return con.protocol.world.map.get_color(x, y, z)
                    x1 += x_inc
                    y1 += y_inc
                    z1 += z_inc
        return tuple(int(a * dist + b * (1 - dist)) for a, b in zip(con.protocol.world.map.get_color(x, y, z), con.color))
    else:
        return con.protocol.world.map.get_color(x, y, z)

@command('light')
def light_cmd(con, radius=None, shadow=False):
    """
    Shortcut for /brush light mode
    /light <radius 1-8> <enable shadow simulation>
    """
    if shadow:
        return brush(con, radius, 'light_shadow')
    else:
        return brush(con, radius, 'light_effect')

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

@command()
def beam(con, length=None, *colors):
    """
    Build a row of blocks with a single click
    /beam <length>
    """
    con.beam_colors = colors
    if length:
        length = int(length)
        if length < 1 or length > 64:
            return 'Length should be between 1-64'
        if con.beam:
            con.beam_length = length
            return 'Beam length changed'
        else:
            con.beam = True
            con.beam_length = length
            return 'Beam mode enabled'
    else:
        if con.beam:
            con.beam = False
            return 'Beam mode disabled'
        else:
            raise ValueError


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
            queue(con, x, y, z, add_dither(color, int(dither)))
        else:
            queue(con, x, y, z, None)
    con.build_queue_start()

@command()
def forestgen(con, sector, dither=3):
    """
    Covers a sector in trees
    /forestgen <sector> <dither>
    """
    add_undo_step(con)
    a = [x**0.5 for x in [0, 1, 2, 4, 5, 8, 9, 10, 13, 16, 17]]
    b = [(x-0.5)**0.5 for x in [1, 3, 5, 7, 9, 13, 15, 19, 21, 23, 25]]
    treetypes = [
        (a, (0,0),(0,0),(1,1),(2,1),(2,1),(2,1),(1,1),(1,1),(1,1),(0,1),(0,1)), # cypress
        (a, (0,0),(0,0),(1,1),(1,1),(2,1),(2,1),(2,1),(2,1),(1,1),(1,1),(1,1),(1,1),(0,1),(0,1),(0,1)), # high cypress
        (a, (0,0),(3,1),(4,1),(3,1),(1,1),(3,1),(1,1),(0,1),(1,1),(0,1),(0,1)), # spruce
        (a, (1,0),(4,1),(7,1),(4,1),(3,1),(4,1),(3,1),(1,1),(3,1),(1,1),(0,1),(1,1),(0,1),(0,1)), # big spruce
        (a, (0,0),(3,1),(4,1),(3,1),(4,1),(3,1),(1,1),(3,1),(1,1),(3,1),(1,1),(0,1),(1,1),(0,1),(1,1),(0,1),(0,1)), # high spruce
        (b, (1,0),(0,0),(3,1),(4,1),(4,1),(3,1),(1,1)),
        (b, (1,0),(0,0),(4,1),(3,1),(4,1),(3,1),(1,1)),
        (b, (1,0),(0,0),(0,0),(1,1),(3,1),(4,1),(3,1),(4,1),(3,1),(1,1)),
        ]
    treetypes += [(a, (1,1),(0,1))] * len(treetypes) # shrub
##    treetypes += [
##        (b, (0,2),(0,2),(1,3),(0,3)), # mushroom
##        (a, (0,2),(0,2),(1,4),(0,4)), # red mushroom
##        ]

    sx, sy = coordinates(sector)
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
                        queue(con, sx+x, sy+y, con.protocol.map.get_height(sx+x, sy+y)-z, add_dither(colors[clr], int(dither)))
    con.build_queue_start()

palette = (
    0xFFFFFF, 0xDC9FB4, 0xE16B8C, 0x8E354A, 0xF8C3CD, 0xF4A7B9, 0x64363C, 0xF596AA, 0xB5495B, 0xE87A90, 0xD05A6E, 0xDB4D6D, 0xFEDFE1, 0x9E7A7A, 0xD0104C, 0x9F353A,
    0xCB1B45, 0xEEA9A9, 0xBF6766, 0x86473F, 0xB19693, 0xEB7A77, 0x954A45, 0xA96360, 0xCB4042, 0xAB3B3A, 0xD7C4BB, 0x904840, 0x734338, 0xC73E3A, 0x554236, 0x994639,
    0xF19483, 0xB54434, 0xB9887D, 0xF17C67, 0x884C3A, 0xE83015, 0xD75455, 0xB55D4C, 0x854836, 0xA35E47, 0xCC543A, 0x724832, 0xF75C2F, 0x6A4028, 0x9A5034, 0xC46243,
    0xAF5F3C, 0xFB966E, 0x724938, 0xB47157, 0xDB8E71, 0xF05E1C, 0xED784A, 0xCA7853, 0xB35C37, 0x563F2E, 0xE3916E, 0x8F5A3C, 0xF0A986, 0xA0674B, 0xC1693C, 0xFB9966,
    0x947A6D, 0xA36336, 0xE79460, 0x7D532C, 0xC78550, 0x985F2A, 0xE1A679, 0x855B32, 0xFC9F4D, 0xFFBA84, 0xE98B2A, 0xE9A368, 0xB17844, 0x96632E, 0xCA7A2C, 0x43341B,
    0xECB88A, 0x78552B, 0xB07736, 0x967249, 0xE2943B, 0xC7802D, 0x9B6E23, 0x6E552F, 0xEBB471, 0xD7B98E, 0x82663A, 0xB68E55, 0xBC9F77, 0x876633, 0xC18A26, 0xFFB11B,
    0xD19826, 0xDDA52D, 0xC99833, 0xF9BF45, 0xDCB879, 0xBA9132, 0xE8B647, 0xF7C242, 0x7D6C46, 0xDAC9A6, 0xFAD689, 0xD9AB42, 0xF6C555, 0xFFC408, 0xEFBB24, 0xCAAD5F,
    0x8D742A, 0xB4A582, 0x877F6C, 0x897D55, 0x74673E, 0xA28C37, 0x6C6024, 0x867835, 0x62592C, 0xE9CD4C, 0xF7D94C, 0xFBE251, 0xD9CD90, 0xADA142, 0xDDD23B, 0xA5A051,
    0xBEC23F, 0x6C6A2D, 0x939650, 0x838A2D, 0xB1B479, 0x616138, 0x4B4E2A, 0x5B622E, 0x4D5139, 0x89916B, 0x90B44B, 0x91AD70, 0xB5CAA0, 0x646A58, 0x7BA23F, 0x86C166,
    0x4A593D, 0x42602D, 0x516E41, 0x91B493, 0x808F7C, 0x1B813E, 0x5DAC81, 0x36563C, 0x227D51, 0xA8D8B9, 0x6A8372, 0x2D6D4B, 0x465D4C, 0x24936E, 0x86A697, 0x00896C,
    0x096148, 0x20604F, 0x0F4C3A, 0x4F726C, 0x00AA90, 0x69B0AC, 0x26453D, 0x66BAB7, 0x268785, 0x405B55, 0x305A56, 0x78C2C4, 0x376B6D, 0xA5DEE4, 0x77969A, 0x6699A1,
    0x81C7D4, 0x33A6B8, 0x0C4842, 0x0D5661, 0x0089A7, 0x336774, 0x255359, 0x1E88A8, 0x566C73, 0x577C8A, 0x58B2DC, 0x2B5F75, 0x3A8FB7, 0x2E5C6E, 0x006284, 0x7DB9DE,
    0x51A8DD, 0x2EA9DF, 0x0B1013, 0x0F2540, 0x08192D, 0x005CAF, 0x0B346E, 0x7B90D2, 0x6E75A4, 0x261E47, 0x113285, 0x4E4F97, 0x211E55, 0x8B81C3, 0x70649A, 0x9B90C2,
    0x8A6BBE, 0x6A4C9C, 0x8F77B5, 0x533D5B, 0xB28FCE, 0x986DB2, 0x77428D, 0x3C2F41, 0x4A225D, 0x66327C, 0x592C63, 0x6F3381, 0x574C57, 0xB481BB, 0x3F2B36, 0x572A3F,
    0x5E3D50, 0x72636E, 0x622954, 0x6D2E5B, 0xC1328E, 0xA8497A, 0x562E37, 0xE03C8A, 0x60373E, 0xFCFAF2, 0xFFFFFB, 0xBDC0BA, 0x91989F, 0x787D7B, 0x707C74, 0x656765,
    0x535953, 0x4F4F48, 0x52433D, 0x373C38, 0x3A3226, 0xEEEEEE, 0xDDDDDD, 0xBBBBBB, 0xAAAAAA, 0x888888, 0x777777, 0x555555, 0x444444, 0x222222, 0x111111, 0x000000
    )

def count_neighbours(field, x, y, w=64):
    x1 = x - 1
    if x1 < 0: x1 = w - 1
    x2 = x + 1
    if x2 >= w: x2 = 0
    y1 = y - 1
    if y1 < 0: y1 = w - 1
    y2 = y + 1
    if y2 >= w: y2 = 0
    n = 0
    for a, b in ((x1, y1), (x, y1), (x2, y1), (x1, y), (x2, y), (x1, y2), (x, y2), (x2, y2)):
        if field[a][b] == 1:
            n += 1
    return n

@command()
def celaut(con, sector, colorshift=0, iterations=32, rules='14'):
    """
    Cellular automaton
    /celaut <sector> <colorshift> <iterations (max 64)> <rules (amount of neighbours for cell to become alive)>
    """
    add_undo_step(con)

    colorshift = int(colorshift)

    iterations = int(iterations)
    if iterations > 64:
        iterations = 64

    rules = tuple(int(x) for x in rules)

    field = [[0 for y in range(64)] for x in range(64)]

    field[31][31] = 1
    field[31][32] = 1
    field[32][31] = 1
    field[32][32] = 1

    field_temp = [x[:] for x in field]

    for i in range(iterations):
        for x in range(64):
            for y in range(64):
                n = count_neighbours(field, x, y)
                if n in rules:
                    field_temp[x][y] = 1
                else:
                    if field[x][y] > 0 and field[x][y] < 255:
                        field_temp[x][y] += 1
        field = [x[:] for x in field_temp]

    sx, sy = coordinates(sector)
    for x in range(64):
        for y in range(64):
            clr = field_temp[x][y] + colorshift
            if clr > 255:
                clr -= 255
            clr = palette[clr]
            clr = ((clr >> 16) & 255, (clr >> 8) & 255, clr & 255)
            queue(con, sx+x, sy+y, con.protocol.map.get_height(sx+x, sy+y)-1, clr)

    con.build_queue_start()

if FN_ENABLED:
    from math import *
    phi = (1+sqrt(5))/2

    @command(admin_only=True)
    def fn(con, *exp):
        """
        /fn <expression>
        """
        if selection(con, fn, exp):
            return
        add_undo_step(con)
        exp = ' '.join(exp)
        for x, y, z in get_points(con):
            value = round(eval(exp)) % 256
            clr = palette[value]
            clr = ((clr >> 16) & 255, (clr >> 8) & 255, clr & 255)
            queue(con, x, y, z, clr)
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
        if con.undo:
            con.redo += [[con.undo[-1][0], []]]
            con.sel_a, con.sel_b = con.undo[-1][0]
            for p in con.undo[-1][1]:
                x, y, z, color = p
                con.redo[-1][1] += [(x, y, z, con.protocol.world.map.get_color(x, y, z))]
                con.build_queue += [(x, y, z, color)]
            con.undo = con.undo[:-1]
        else:
            break
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
        if con.redo:
            con.undo += [[con.redo[-1][0], []]]
            con.sel_a, con.sel_b = con.redo[-1][0]
            for p in con.redo[-1][1]:
                x, y, z, color = p
                con.undo[-1][1] += [(x, y, z, con.protocol.world.map.get_color(x, y, z))]
                con.build_queue += [(x, y, z, color)]
            con.redo = con.redo[:-1]
        else:
            break
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
            self.brush_source = None
            self.clipboard = []
            self.highlighted_blocks = []
            self.beam = False
            self.beam_colors = None
            self.beam_length = None
            self.beam_in_progress = False

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
                            highlight_selection(self)
                            self.send_chat('Selection created [%sx%sx%s]. Use /u to remove selection' % tuple([max(x)-min(x)+1 for x in zip(self.sel_a, self.sel_b)]))
                            if self.deferred:
                                func, args = self.deferred
                                func(self, *args)
                                self.deferred = None
                        else:
                            self.sel_a = list(coords)
                            highlight_selection(self)
                            self.send_chat('First corner has been selected')
            connection.on_shoot_set(self, state)

        def on_secondary_fire_set(self, state):
            if state == True:
                if self.brush and 'light_' not in self.brush_mode:
                    coords = self.world_object.cast_ray(64)
                    if coords:
                        brush_build(self, *list(coords), 'destroy')
                if self.selection:
                    coords = self.world_object.cast_ray(32)
                    if coords:
                        self.sel_a = list(coords)
                        highlight_selection(self)
                        self.send_chat('First corner has been redefined')
            connection.on_secondary_fire_set(self, state)

        def on_block_destroy(self, x, y, z, value):
            if self.selection:
                if self.sel_a:
                    self.sel_b = [x, y, z]
                    highlight_selection(self)
                    self.send_chat('Selection created [%sx%sx%s]. Use /u to remove selection' % tuple([max(x)-min(x)+1 for x in zip(self.sel_a, self.sel_b)]))
                    if self.deferred:
                        func, args = self.deferred
                        func(self, *args)
                        self.deferred = None
                else:
                    self.sel_a = [x, y, z]
                    highlight_selection(self)
                    self.send_chat('First corner has been selected')
                return False
            if self.beam and not self.beam_in_progress:
                if self.build_queue == []:
                    self.beam_in_progress = True
                    ori = self.world_object.orientation
                    ori = (ori.x, ori.y)
                    ori_abs = [abs(x) for x in ori]
                    i = ori_abs.index(max(ori_abs))
                    sign = int(ori[i]/abs(ori[i]))
                    self.sel_a = [x, y, z]
                    self.sel_b = self.sel_a.copy()
                    self.sel_b[i] += (self.beam_length - 1) * sign
                    replace(self, 'any', ('remove',))
                    return False
            if connection.on_block_destroy(self, x, y, z, value) == False:
                return False

        def on_block_build_attempt(self, x, y, z):
            if self.selection:
                if self.sel_a:
                    self.sel_b = [x, y, z]
                    highlight_selection(self)
                    self.send_chat('Selection created [%sx%sx%s]. Use /u to remove selection' % tuple([max(x)-min(x)+1 for x in zip(self.sel_a, self.sel_b)]))
                    if self.deferred:
                        func, args = self.deferred
                        func(self, *args)
                        self.deferred = None
                else:
                    self.sel_a = [x, y, z]
                    highlight_selection(self)
                    self.send_chat('First corner has been selected')
                return False
            if self.beam and not self.beam_in_progress:
                if self.build_queue == []:
                    self.beam_in_progress = True
                    ori = self.world_object.orientation
                    ori = (ori.x, ori.y)
                    ori_abs = [abs(x) for x in ori]
                    i = ori_abs.index(max(ori_abs))
                    sign = int(ori[i]/abs(ori[i]))
                    self.sel_a = [x, y, z]
                    self.sel_b = self.sel_a.copy()
                    self.sel_b[i] += (self.beam_length - 1) * sign
                    replace(self, 'any', self.beam_colors)
                    return False
            if connection.on_block_build_attempt(self, x, y, z) == False:
                return False

        def on_block_build(self, x, y, z):
            if connection.on_block_build(self, x, y, z) == False:
                return False

        def build_queue_start(self):
            self.build_queue_len = len(self.build_queue)
##            self.build_queue = sorted(self.build_queue, key=lambda x: (x[3] is not None, x[3])) # blocks queued for removal should be processed first
            self.build_queue = iter(self.build_queue)
            self.build_queue_loop = LoopingCall(self.build_queue_batch)
            self.build_queue_loop.start(0.02)

        def build_queue_batch(self):
            for _ in range(120):
                try:
                    block = next(self.build_queue)
                    if block:
                        if build(self, *block) == False:
                            self.build_queue_loop.stop()
                            self.build_queue = []
                            highlight_selection(self)
                            if self.brush == False and self.beam == False:
                                self.send_chat('%s block(s) have been changed' % self.build_queue_len)
                            if self.beam_in_progress:
                                self.beam_in_progress = False
                            break
                except:
                    self.build_queue_loop.stop()
                    self.build_queue = []
                    highlight_selection(self)
                    if self.brush == False and self.beam == False:
                        self.send_chat('%s block(s) have been changed' % self.build_queue_len)
                    if self.beam_in_progress:
                        self.beam_in_progress = False
                    break

    return protocol, CTConnection
