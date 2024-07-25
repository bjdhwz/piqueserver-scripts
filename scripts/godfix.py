"""
Makes it so hitting a player no longer disables god mode.

Should always be first in scripts list in config to not break other scripts that use on_hit!

.. codeauthor:: Liza
"""

def apply_script(protocol, connection, config):
    class GodfixConnection(connection):

        def on_hit(self, hit_amount, player, _type, grenade):
            if not self.protocol.killing:
                self.send_chat(
                    "You can't kill anyone right now! Damage is turned OFF")
                return False
            if not self.killing:
                self.send_chat("%s. You can't kill anyone." % player.name)
                return False

    return protocol, GodfixConnection
