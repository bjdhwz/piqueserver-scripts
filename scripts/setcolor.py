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

from random import choice
from piqueserver.commands import command
from pyspades.common import make_color
from pyspades.contained import SetColor


@command('clr', 'setcolor', 'color')
def setcolor(connection, *args):
    """
    Set current block color
    /clr <r> <g> <b>, /clr <#aabbcc>, /clr <#abc>, no arguments to get random color or /clr ? to get current color
    """
    if len(args) == 3:
        rgb = tuple(int(x) for x in args)
    elif len(args) == 1:
        if args[0] == '?':
            return '#%02X%02X%02X ' % connection.color + str(connection.color)
        else:
            h = args[0].strip('#')
            if len(h) == 3:
                h = ''.join([x*2 for x in h])
            rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    else:
        rgb = choice(range(255)), choice(range(255)), choice(range(255))

    set_color = SetColor()
    set_color.value = make_color(*rgb)
    set_color.player_id = connection.player_id
    connection.protocol.broadcast_contained(set_color)
    connection.color = rgb


def apply_script(protocol, connection, config):
    return protocol, connection
