"""
Increases max chat message length and automatically wraps it if it doesn't fit in a single line.

.. codeauthor:: Liza
"""

import shlex, textwrap
from twisted.logger import Logger
from typing import Dict, Optional, Sequence, Tuple
from pyspades import contained as loaders
from pyspades.constants import *
from pyspades.packet import register_packet_handler

log = Logger()

## 108 - original piqueserver chat message limit. Used as line wrap length.
## 199 - max length that can be typed in through OpenSpades in-game interface at 1920x1080 resolution. Longer messages can only be pasted in.
## 216 - two lines wrap length.
## 255 - max length that can be pasted into OpenSpades.
MAX_CHAT_MSG_LEN = 255


def parse_command(value: str) -> Tuple[str, Sequence[str]]:
    try:
        splitted = shlex.split(value)
    except ValueError:
        splitted = value.split(' ')
    if splitted:
        command = splitted.pop(0)
    else:
        command = ''
    return command, splitted


def apply_script(protocol, connection, config):
    class LongMessagesConnection(connection):

        @register_packet_handler(loaders.ChatMessage)
        def on_chat_message_recieved(self, contained: loaders.ChatMessage) -> None:
            if not self.name:
                return

            value = contained.value
            if len(value) > MAX_CHAT_MSG_LEN:
                log.info("TOO LONG MESSAGE (%i chars) FROM %s (#%i)" %
                         (len(value), self.name, self.player_id))

            value = value[:MAX_CHAT_MSG_LEN]
            if value.startswith('/'):
                self.on_command(*parse_command(value[1:]))
            else:
                value = '\n'.join(textwrap.wrap(value, 108))
                global_message = contained.chat_type == CHAT_ALL
                result = self.on_chat(value, global_message)
                if result == False:
                    return
                elif result is not None:
                    value = result
                contained.chat_type = CHAT_ALL if global_message else CHAT_TEAM
                contained.value = value
                contained.player_id = self.player_id
                if global_message:
                    team = None
                else:
                    team = self.team
                for player in self.protocol.players.values():
                    if self.shadowbanned:
                        if player == self:
                            player.send_contained(contained)
                        if player.admin:
                            player.send_chat('[SHADOW] %s: %s' % (self.name, value))
                    else:
                        if not player.deaf:
                            if team is None or team is player.team:
                                player.send_contained(contained)
                self.on_chat_sent(value, global_message)

    return protocol, LongMessagesConnection
