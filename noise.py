"""
Build using slightly randomized colors

Commands
^^^^^^^^

* ``/noise <value>`` higher values make color more random

.. codeauthor:: Liza
"""

from random import choice
from piqueserver.commands import command
from pyspades.common import make_color
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from pyspades.contained import BlockAction, SetColor
from pyspades import contained as loaders


@command('noise', 'n')
def noise(connection, value=2):
    """
    Toggle noisy colors
    /noise <value> - higher values make color more random
    """
    try:
        value = int(value)
    except:
        return 'Value should be a number'
    if connection.building_noise:
        connection.building_noise = 0
        return 'Noise mode disabled'
    else:
        connection.building_noise = value
        return 'Noise mode enabled'

def build(con, x, y, z):
    noise = choice(range(-con.building_noise-1, con.building_noise))
    rgb = [value + noise for value in con.color]
    rgb = [255 if value > 255 else value for value in rgb]
    rgb = tuple([0 if value < 0 else value for value in rgb])

    set_color = SetColor()
    set_color.player_id = con.player_id
    set_color.value = make_color(*rgb)
    con.protocol.broadcast_contained(set_color)

    block_action = BlockAction()
    block_action.player_id = con.player_id
    block_action.value = BUILD_BLOCK
    block_action.x = x
    block_action.y = y
    block_action.z = z
    con.protocol.broadcast_contained(block_action)

    con.protocol.map.set_point(x, y, z, rgb)


def apply_script(protocol, connection, config):
    class NoiseBuildConnection(connection):
        building_noise = 0

        def on_block_build_attempt(self, x, y, z):
            if connection.on_block_build_attempt(self, x, y, z) == False:
                return False
            if self.building_noise:
                build(self, x, y, z)
                connection.on_block_build(self, x, y, z)
                return False

        def on_line_build_attempt(self, points):
            if connection.on_line_build_attempt(self, points) == False:
                return False
            if self.building_noise:
                for point in points:
                    build(self, *point)
                connection.on_line_build(self, points)
                return False

    return protocol, NoiseBuildConnection
