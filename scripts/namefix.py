"""
Kicks players with ASCII control characters in name.

.. codeauthor:: Liza
"""

from twisted.logger import Logger
from pyspades.common import escape_control_codes

log = Logger()


def apply_script(protocol, connection, config):
    class LogClientConnection(connection):

        def on_login(self, name):
            if name != escape_control_codes(name):
                self.kick(silent=True)
                log.info("'%s' was kicked for control codes in name" % escape_control_codes(name))
            else:
                connection.on_login(self, name)

    return protocol, LogClientConnection
