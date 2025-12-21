"""
Kick players with ASCII control characters, and, optionally, with confounding "#" in the beginning of their names.

.. codeauthor:: Liza
"""

from twisted.logger import Logger
from pyspades.common import escape_control_codes

KICK_HASHSIGN = True

confounding_names = ['#' + str(x) for x in range(32)]

log = Logger()


def apply_script(protocol, connection, config):
    class LogClientConnection(connection):

        def on_login(self, name):
            if name != escape_control_codes(name):
                self.kick(silent=True)
                log.info("'%s' was kicked for control codes in name" % escape_control_codes(name))
            elif KICK_HASHSIGN and name in confounding_names:
                self.kick(silent=True)
                log.info("'%s' was kicked for confounding name" % escape_control_codes(name))
            else:
                connection.on_login(self, name)

    return protocol, LogClientConnection
