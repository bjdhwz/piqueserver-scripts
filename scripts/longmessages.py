"""
Increases max chat message length and automatically wraps it if it doesn't fit in a single line.
Compatible with shadowban.py and ignore.py

Commands
^^^^^^^^

* ``/nocaps <player>`` makes player's messages properly cased

.. codeauthor:: Liza
"""

import os, shlex, textwrap
from twisted.logger import Logger
from typing import Dict, Optional, Sequence, Tuple
from piqueserver.commands import command, target_player
from piqueserver.config import config
from pyspades import contained as loaders
from pyspades.constants import *
from pyspades.packet import register_packet_handler

log = Logger()

## 100 - apparently 108 might be too long for IV of Spades client. Used as line wrap length.
## 108 - original piqueserver chat message limit.
## 199 - max length that can be typed in through OpenSpades in-game interface at 1920x1080 resolution. Longer messages can only be pasted in and should contain line breaks.
## 255 - max length that can be pasted into OpenSpades.
MAX_CHAT_MSG_LEN = 255

PREFIXES = []

try:
    with open(os.path.join(config.config_dir, 'player_prefixes.txt')) as f:
        players = f.read().splitlines()
        PREFIXES = {x.split('\t', 1)[1]:x.split('\t', 1)[0] for x in players}
except:
    f = open(os.path.join(config.config_dir, 'player_prefixes.txt'), 'w')
    f.close()


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

translit_table = {
    # Cyrillic
    'А': 'A',  'а': 'a',
    'Б': 'B',  'б': 'b',
    'В': 'V',  'в': 'v',
    'Г': 'G',  'г': 'g',
    'Д': 'D',  'д': 'd',
    'Е': 'E',  'е': 'e',
    'Ё': 'Yo', 'ё': 'yo',
    'Ж': 'Zh', 'ж': 'zh',
    'З': 'Z',  'з': 'z',
    'И': 'I',  'и': 'i',
    'Й': 'Y',  'й': 'y',
    'К': 'K',  'к': 'k',
    'Л': 'L',  'л': 'l',
    'М': 'M',  'м': 'm',
    'Н': 'N',  'н': 'n',
    'О': 'O',  'о': 'o',
    'П': 'P',  'п': 'p',
    'Р': 'R',  'р': 'r',
    'С': 'S',  'с': 's',
    'Т': 'T',  'т': 't',
    'У': 'U',  'у': 'u',
    'Ф': 'F',  'ф': 'f',
    'Х': 'Kh', 'х': 'kh',
    'Ц': 'C',  'ц': 'c',
    'Ч': 'Ch', 'ч': 'ch',
    'Ш': 'Sh', 'ш': 'sh',
    'Щ': 'Sch','щ': 'sch',
    'Ъ': '',   'ъ': '',
    'Ы': 'Y',  'ы': 'y',
    'Ь': "'",  'ь': "'",
    'Э': 'E',  'э': 'e',
    'Ю': 'Yu', 'ю': 'yu',
    'Я': 'Ya', 'я': 'ya',

    'І': 'I', 'і': 'i',
    'Ї': 'Yi', 'ї': 'yi',
    'Є': 'Ye', 'є': 'ye',
    'Ґ': 'G', 'ґ': 'g',
    'Ў': 'W', 'ў': 'w',
    'Ј': 'J', 'ј': 'j',
    'Љ': 'Lj', 'љ': 'lj',
    'Њ': 'Nj', 'њ': 'nj',
    'Ћ': 'C', 'ћ': 'c',
    'Џ': 'Dz', 'џ': 'dz',
    'Ә': 'E', 'ә': 'e',
    'Ӕ': 'Ae', 'ӕ': 'ae',
    'Ғ': 'Gh', 'ғ': 'gh',
    'Ң': 'Ng', 'ң': 'ng',
    'Ө': '"Oe', 'ө': 'oe',
    'Ү': 'Y', 'ү': 'y',
    'Ұ': 'U', 'ұ': 'u',
    'Ҷ': 'J', 'ҷ': 'j',

    # Extended Latin
    'Ç': 'C', 'ç': 'c',
    'Á': 'A', 'á': 'a',
    'É': 'E', 'é': 'e',
    'Ó': 'O', 'ó': 'o',
    'Ú': 'U', 'ú': 'u',
    'Ä': 'Ae', 'ä': 'ae',
    'Ö': 'Oe', 'ö': 'oe',
    'Ü': 'Ue', 'ü': 'ue',
    'Ą': 'A', 'ą': 'a',
    'Ę': 'E', 'ę': 'e',
    'Ł': 'L', 'ł': 'l',
    'Ń': 'N', 'ń': 'n',
    'Ś': 'S', 'ś': 's',
    'Ź': 'Z', 'ź': 'z',
    'Ż': 'Z', 'ż': 'z',
    'Č': 'C', 'č': 'c',
    'Ć': 'C', 'ć': 'c',
    'Đ': 'D', 'đ': 'd',
    'Š': 'S', 'š': 's',
    'Ž': 'Z', 'ž': 'z',
    'Ğ': 'G', 'ğ': 'g',
    'I': 'I', 'ı': 'i',
    'İ': 'I', 'i': 'i',
    'Ş': 'S', 'ş': 's',
    }

def transliterate(value):
    msg = []
    for char in value:
        if char in translit_table:
            msg += [translit_table[char]]
        else:
            msg += [char]
    return ''.join(msg)


@command(admin_only=True)
@target_player
def nocaps(connection, player):
    """
    Makes player's messages properly cased
    /nocaps <player>
    """
    if player.name in connection.protocol.nocaps:
        connection.protocol.nocaps.remove(player.name)
        return "Anticaps is no longer active for %s" % player.name
    else:
        connection.protocol.nocaps += [player.name]
        connection.protocol.broadcast_chat("Anticaps is now active for %s" % player.name)


def apply_script(protocol, connection, config):
    class LongMessagesProtocol(protocol):

        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.nocaps = []

    class LongMessagesConnection(connection):
        shadowbanned = False

        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.ignored = []

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
                value = '\n'.join(textwrap.wrap(value, 100))
                global_message = contained.chat_type == CHAT_ALL
                result = self.on_chat(value, global_message)
                if result == False:
                    return
                elif result is not None:
                    value = result
                contained.chat_type = CHAT_ALL if global_message else CHAT_TEAM
                if self.name in self.protocol.nocaps:
                    value = value.capitalize().replace(' i ', ' I ').replace("i'd", "I'd").replace("i'm", "I'm").replace("i've", "I've").replace(' i,', ' I,')
                contained.value = value
                contained.player_id = self.player_id
                if global_message:
                    team = None
                else:
                    team = self.team
                for player in self.protocol.players.values():
                    if 'Voxlap' in player.client_string or 'BetterSpades' in player.client_string:
                        contained.value = transliterate(value)
                    if self.shadowbanned:
                        if player == self:
                            player.send_contained(contained)
                        if player.admin:
                            player.send_chat('[Shadow] %s: %s' % (self.name, value))
                    else:
                        if not player.deaf:
                            if team is None or team is player.team:
                                if not self.name in player.ignored:
                                    if self.name in PREFIXES:
                                        teamcolor = ''
                                        if self.team.id == 0:
                                            teamcolor = '\1'
                                        elif self.team.id == 1:
                                            teamcolor = '\2'
                                        player.send_chat('[%s] %s%s\6: %s \0' % (PREFIXES[self.name], teamcolor, self.name, value))
                                    else:
                                        player.send_contained(contained)
                self.on_chat_sent(value, global_message)

    return LongMessagesProtocol, LongMessagesConnection
