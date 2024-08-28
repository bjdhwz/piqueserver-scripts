"""
Make gradient lines!

/gradient r g b r g b

alias: /gr

Author: infogulch
"""

from pyspades.common import make_color
from pyspades.contained import BlockAction, SetColor
from pyspades.constants import *
from piqueserver.commands import command

from cbc.core import buildingstate
import cbc


@command('gradient', 'gr')
def gradient(connection, *colors):
    if len(colors) == 0:
        if connection.state:
            connection.state = None
        else:
            connection.state = GradientState(connection)
        return
    elif len(colors) != 6:
            return 'Usage: /gradient r g b r g b, OR choose from & to colors with /grf /grt'
    try:
        colors = tuple(int(c) for c in colors)
        connection.gradient_colors = colors[:3], colors[3:]
        connection.state = GradientState(connection)
    except ValueError:
        return 'All args must be integers.'


@command('gradientfrom', 'grf')
def gradient_from(connection):
    connection.gradient_colors[0] = connection.color
    return 'Gradient from color is now: ({}, {}, {})'.format(*connection.color)


@command('gradientto', 'grt')
def gradient_to(connection):
    connection.gradient_colors[1] = connection.color
    return 'Gradient to color is now: ({}, {}, {})'.format(*connection.color)


def build_gradient_line(protocol, colors, points):
    sp = cbc.core.cbc.ServerPlayer()
    
    block_action = BlockAction()
    block_action.player_id = sp.player_id
    block_action.value = BUILD_BLOCK
    
    set_color = SetColor()
    set_color.player_id = sp.player_id
    
    color_range = list(zip(*colors))
    
    lp = len(points) - 1
    map_ = protocol.map
    for i in range(len(points)):
        pct = 1 - (i+0.0) / lp, (i+0.0) / lp if lp else (1, 0)
        color = tuple(int(round(sum(c*p for c, p in zip(crng, pct)))) for crng in color_range)

        map_.set_point(*points[i], color=color)
        
        set_color.value = make_color(*color)
        protocol.broadcast_contained(set_color, save=True)
        
        block_action.x, block_action.y, block_action.z = points[i]
        protocol.broadcast_contained(block_action, save=True)


class GradientState(buildingstate.BuildingState):
    START_MESSAGE = 'You are now in *Gradient* mode'
    CANCEL_MESSAGE = 'You are no longer in *Gradient* mode'

    def on_line_build_attempt(self, points):
        for point in points:
            if self.player.on_block_build_attempt(*point) == False:
                return False
        build_gradient_line(self.player.protocol, self.player.gradient_colors, points)
        return False


def apply_script(protocol, connection, config):
    protocol, connection = buildingstate.apply_script(protocol, connection, config)

    class GradientConnection(connection):
        def __init__(self, *args, **kwargs):
            connection.__init__(self, *args, **kwargs)
            self.gradient_colors = [(0, 0, 0), (0, 0, 0)]

    return protocol, GradientConnection
