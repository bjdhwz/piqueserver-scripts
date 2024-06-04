"""
Send message to all admins currently online

Commands
^^^^^^^^

* ``/ <message>`` - just slash is enough

.. codeauthor:: Liza
"""

import random, re
from piqueserver.commands import command, join_arguments
from pyspades.common import make_color
from pyspades.contained import SetColor, ChatMessage


@command('a', '/')
def adminchannel(connection, *arg):
    """
    Send message to all admins currently online
    /a <message> or / <message> (just slash is enough)
    """
    message = join_arguments(arg)
    if not message:
        return 'Enter a message you want to send'
    for player in connection.protocol.players.values():
        if player.admin:
            player.send_chat('[Admin] <%s>: %s' % (connection.name, message))


def apply_script(protocol, connection, config):
    return protocol, connection
