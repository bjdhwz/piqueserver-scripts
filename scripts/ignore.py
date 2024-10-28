"""
Ignore messages from a player and publicly announce it.
Requires longmessages.py

.. codeauthor:: Liza
"""

from piqueserver.commands import command, target_player


@command()
@target_player
def ignore(connection, player):
    """
    Ignore messages from a player and publicly announce it
    /ignore <player>
    """
    if connection.name == player.name:
        return "Write name of the player you want to ignore"
    if player.name in connection.ignored:
        connection.ignored.remove(player.name)
##        connection.protocol.broadcast_chat("%s sees messages by %s again" % (connection.name, player.name))
        return "You no longer ignore %s" % player.name
    else:
        connection.ignored += [player.name]
        connection.protocol.broadcast_chat("%s now ignores messages sent by %s" % (connection.name, player.name))
        return "You now ignore %s" % player.name


def apply_script(protocol, connection, config):
    class IgnoreConnection(connection):

        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.ignored = []

    return protocol, IgnoreConnection
