"""
Spawn grenades with given parameters.

Commands
^^^^^^^^

* ``/nade <amount> <spawn radius> <velocity> <fuse (can be constant X or range X-Y)>``

.. codeauthor:: Liza
"""

from piqueserver.commands import command
from pyspades.common import Vertex3
from pyspades.contained import GrenadePacket
from pyspades.world import Grenade
import random
from twisted.internet.reactor import callLater


@command(admin_only=True)
def nade(con, num='1', radius='0', speed='0', fuse='3'):
    """
    Spawn grenades with given parameters
    /nade <amount> <spawn radius> <velocity> <fuse (can be constant X or range X-Y)>
    """
    radius = float(radius)
    speed = float(speed)
    x, y, z = con.get_location()
    xy = [x-radius, x+radius, y-radius, y+radius]
    xy = [i if i >= 0 else 0 for i in xy]
    xy = [i if i <= 511 else 511 for i in xy]
    x1, x2, y1, y2 = xy
    if '-' in fuse:
        fuse_start, fuse_end = fuse.split('-')
    else:
        fuse_start = fuse_end = fuse
    fuse_start = float(fuse_start)
    fuse_end = float(fuse_end)
    if fuse_start > 60:
        fuse_start = 60
    if fuse_end > 60:
        fuse_end = 60
    for i in range(int(num)):
        fuse = random.uniform(fuse_start, fuse_end)
        pos = Vertex3(random.uniform(x1, x2), random.uniform(y1, y2), z)
        orientation = None
        velocity = Vertex3(
            random.uniform(-speed, speed),
            random.uniform(-speed, speed),
            random.uniform(-speed, speed)
            )
        grenade = con.protocol.world.create_object(
            Grenade,
            fuse,
            pos,
            orientation,
            velocity,
            con.grenade_exploded)
        grenade.name = 'nadefun'
        grenade_packet = GrenadePacket()
        grenade_packet.value = fuse
        grenade_packet.player_id = 32
        grenade_packet.position = pos.get()
        grenade_packet.velocity = velocity.get()
        con.protocol.broadcast_contained(grenade_packet)


def apply_script(protocol, connection, config):
    return protocol, connection
