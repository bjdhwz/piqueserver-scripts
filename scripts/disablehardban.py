"""
Disables hardban functionality of piqueserver to prevent false bans due to bugs in scripts

.. codeauthor:: Liza
"""

from pyspades.bytes import NoDataLeft
from pyspades.server import ServerProtocol
from twisted.internet import reactor
from twisted.logger import (FilteringLogObserver, Logger, LogLevel,
                            LogLevelFilterPredicate, globalLogBeginner,
                            textFileLogObserver)

log = Logger()


def apply_script(protocol, connection, config):
    class DisableHardbanProtocol(protocol):

        def data_received(self, peer, packet):
            ip = peer.address.host
            current_time = reactor.seconds()
            try:
                ServerProtocol.data_received(self, peer, packet)
            except (NoDataLeft, ValueError):
                import traceback
                traceback.print_exc()
                log.info(
                    'IP {ip} triggered hardban conditions.',
                    ip=ip
                )
##                self.hard_bans.add(ip)
                return
            dt = reactor.seconds() - current_time
            if dt > 1.0:
                log.warn('processing {data!r} from {ip} took {time}',
                         data=packet.data,
                         ip=ip,
                         time=dt)

    return DisableHardbanProtocol, connection
