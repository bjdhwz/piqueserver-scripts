"""
Write client string to log

.. codeauthor:: Liza
"""

from twisted.logger import Logger
from pyspades.common import escape_control_codes

log = Logger()


def apply_script(protocol, connection, config):
    class LogClientConnection(connection):

        def on_login(self, name):
            connection.on_login(self, name)
            log.info('{name} uses {client}',
                     name=self.printable_name,
                     client=escape_control_codes(self.client_string))

    return protocol, LogClientConnection
