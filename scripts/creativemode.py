"""
1) Disables flag capture
2) Hides tents and intel from the map
3) Disables grenade damage
4) Enables teamkill for Blue team and disables all killing for Green team, creating 'PVP' and 'Peace' teams

Commands
^^^^^^^^

* ``/flag <1|2> <hide>`` bring intel to your current location or hide it

.. codeauthor:: Liza
"""

from piqueserver.commands import command

HIDE_POS = (-256, -256, 63)


@command(admin_only=True)
def flag(connection, team, hide=False):
    """
    Allows to use intel for decorative purposes
    /flag <1|2> <hide> - bring intel to your current location or hide it
    """
    if team == '1':
        flag = connection.protocol.team_1.flag
    elif team == '2':
        flag = connection.protocol.team_2.flag
    else:
        return "Usage: /flag <1|2> <hide>"

    if hide:
        flag.set(*HIDE_POS)
    else:
        x, y, z = [round(x*2)/2 for x in connection.get_location()]
        flag.set(x, y, z+2.5)
    flag.update()


def apply_script(protocol, connection, config):
    class NoCaptureConnection(connection):

        def on_flag_take(self):
            return False

        def on_flag_drop(self):
            return False

        def on_flag_capture(self):
            return False

        def capture_flag(self):
            return False

##        def on_team_join(self, team): # all players in a single team
##            if team == self.protocol.team_1:
##                team = self.protocol.team_2
##            return team

        def on_hit(self, hit_amount, player, _type, grenade):
            if connection.on_hit(self, hit_amount, player, _type, grenade) == False:
                return False
            if self.team.id == 0:
                if player.team.id == 1:
                    return False
            if self.team.id == 1:
                return False

        def on_block_destroy(self, x, y, z, value):
            if value == 3: # disables grenade damage
                return False
            if connection.on_block_destroy(self, x, y, z, value) == False:
                return False

    class NoCaptureProtocol(protocol):

        def on_base_spawn(self, x, y, z, base, entity_id):
            return HIDE_POS

        def on_flag_spawn(self, x, y, z, flag, entity_id):
            return HIDE_POS

    return NoCaptureProtocol, NoCaptureConnection
