"""
Build using slightly randomized colors.

Commands
^^^^^^^^

* ``/dither <value>`` higher values make color more random

.. codeauthor:: Liza
"""

from random import choice
from piqueserver.commands import command
from pyspades.common import make_color
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from pyspades.contained import BlockAction, SetColor
from pyspades import contained as loaders


@command('dither', 'd')
def dither(con, value=3):
    """
    Toggle color dithering
    /dither <1-127> - higher values make colors more random
    """
    try:
        v = int(value)
    except:
        return 'Value should be a whole number'
    if v > 127:
        v = 127
    if v < 0:
        v = 0
    if type(value) == type(''): # user entered value
        if con.dithering == v:
            con.dithering = 0
            return 'Color dithering disabled'
        else:
            if con.dithering:
                con.dithering = v
                return 'Color dithering value changed'
            else:
                con.dithering = v
                return 'Color dithering enabled'
    else: # user didn't enter value
        if con.dithering:
            con.dithering = 0
            return 'Color dithering disabled'
        else:
            con.dithering = v
            return 'Color dithering enabled'

def set_dither(con, x, y, z):
    noise = choice(range(-con.dithering-1, con.dithering))
    rgb = [value + noise for value in con.dithercolor]
    rgb = [255 if value > 255 else value for value in rgb]
    rgb = tuple([0 if value < 0 else value for value in rgb])

    set_color = SetColor()
    set_color.player_id = con.player_id
    set_color.value = make_color(*rgb)
    con.protocol.broadcast_contained(set_color)
    con.color = rgb

def build(con, x, y, z):
    if con.on_block_build_attempt(x, y, z) == False:
        return
    block_action = BlockAction()
    block_action.player_id = con.player_id
    block_action.x = x
    block_action.y = y
    block_action.z = z
    block_action.value = DESTROY_BLOCK
    con.protocol.broadcast_contained(block_action, save=True)
    block_action.value = BUILD_BLOCK
    con.protocol.broadcast_contained(block_action, save=True)
    con.protocol.map.set_point(x, y, z, con.color)


def apply_script(protocol, connection, config):
    class DitheringConnection(connection):
        dithering = 0

        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.dithercolor = None

        def on_color_set(self, color):
            self.dithercolor = color
            connection.on_color_set(self, color)

        def on_block_build_attempt(self, x, y, z):
            if connection.on_block_build_attempt(self, x, y, z) == False:
                return False
            if self.dithering:
                set_dither(self, x, y, z)
                connection.on_block_build(self, x, y, z) # for block logging

        def on_line_build_attempt(self, points):
            if connection.on_line_build_attempt(self, points) == False:
                return False
            if self.dithering:
                for point in points:
                    set_dither(self, *point)
                    build(self, *point)
                    connection.on_block_build(self, *point) # for block logging
                return False

    return protocol, DitheringConnection
