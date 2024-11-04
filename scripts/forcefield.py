"""
Adds a toggleable "forcefield" that pushes players away.

Commands
^^^^^^^^

* ``/forcefield``

.. codeauthor:: Liza
"""

from piqueserver.commands import command
from twisted.internet.task import LoopingCall


@command('forcefield', 'ff')
def forcefield(connection):
    """
    Toggle a "forcefield" that pushes away other players if they get to close to you
    /forcefield
    """
    if connection.forcefield:
        connection.forcefield = False
        return "Forcefield disabled"
    else:
        connection.forcefield = True
        return "Forcefield enabled"


def apply_script(protocol, connection, config): # maybe use on_move?
    class ForcefieldConnection(connection):
        forcefield = False
        forcefield_loop = False

        def forcefield_check(self):
            x1, y1, z1 = self.world_object.position.get()
            for player in self.protocol.players.values():
                if not player.world_object:
                    return
                if self.forcefield or player.forcefield:
                    if self.player_id != player.player_id:
                        x2, y2, z2 = player.world_object.position.get()
                        dist = ((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)**0.5
                        if dist < 4.5:
                            vel_a = self.world_object.velocity
                            vel_b = player.world_object.velocity
                            if abs(vel_a.x) + abs(vel_a.y) + abs(vel_a.z) > abs(vel_b.x) + abs(vel_b.y) + abs(vel_b.z):
                                self.set_location_safe((x1 + x1 - x2, y1 + y1 - y2, z1))

        def on_spawn(self, pos):
            if not self.forcefield_loop:
                self.forcefield_loop = LoopingCall(self.forcefield_check)
                self.forcefield_loop.start(0.2)
            return connection.on_spawn(self, pos)

        def on_disconnect(self):
            try:
                self.forcefield_loop.stop()
            except:
                pass
            return connection.on_disconnect(self)

    return protocol, ForcefieldConnection
