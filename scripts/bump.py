"""
Makes players "physical", allowing them to push each other slightly.

Commands
^^^^^^^^

* ``/nobump`` toggle bumping for yourself

.. codeauthor:: Liza
"""

import os
from piqueserver.commands import command
from piqueserver.config import config
from twisted.internet.task import LoopingCall


NOBUMP = []

try:
    with open(os.path.join(config.config_dir, 'no_bump.txt')) as f:
        NOBUMP = f.read().splitlines()
except:
    f = open(os.path.join(config.config_dir, 'no_bump.txt'), 'w')
    f.close()

@command()
def nobump(connection):
    """
    Toggle bumping
    /nobump
    """
    connection.bumping = not connection.bumping
    if connection.name in NOBUMP:
        NOBUMP.remove(connection.name)
        connection.bump_loop = LoopingCall(connection.bump_check)
        connection.bump_loop.start(0.15)
        connection.send_chat('Bumping has been enabled')
    else:
        NOBUMP.append(connection.name)
        connection.bump_loop.stop()
        connection.send_chat('Bumping has been disabled')
    with open(os.path.join(config.config_dir, 'no_bump.txt'), 'w') as f:
        f.write('\n'.join(NOBUMP))


def apply_script(protocol, connection, config):
    class BumpConnection(connection):
        bumping = False
        bump_loop = False

        def bump_check(self):
            x1, y1, z1 = self.world_object.position.get()
            for player in self.protocol.players.values():
                if not player.world_object:
                    return
                if self.bumping and player.bumping:
                    if self.player_id != player.player_id:
                        x2, y2, z2 = player.world_object.position.get()
                        dist = ((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)**0.5
                        if dist < 1.0:
                            vel_a = self.world_object.velocity
                            vel_b = player.world_object.velocity
                            try: # ignore division by zero from zero velocity
                                if abs(vel_a.x) > abs(vel_a.y):
                                    self.set_location((x1 - vel_a.x/abs(vel_a.x) * 1.2 - 0.5, y1 - vel_a.y - 0.5, z1 + 0.5))
                                else:
                                    self.set_location((x1 - vel_a.x - 0.5, y1 - vel_a.y/abs(vel_a.y) * 1.2 - 0.5, z1 + 0.5))
                                player.set_location((x2 + vel_a.x - 0.5, y2 + vel_a.y - 0.5, z2 + 0.5))
                            except:
                                pass

        def on_spawn(self, pos):
            if self.name not in NOBUMP:
                self.bumping = True
                if not self.bump_loop:
                    self.bump_loop = LoopingCall(self.bump_check)
                    self.bump_loop.start(0.2)
            return connection.on_spawn(self, pos)

        def on_disconnect(self):
            try:
                self.bump_loop.stop()
            except:
                pass
            return connection.on_disconnect(self)

    return protocol, BumpConnection
