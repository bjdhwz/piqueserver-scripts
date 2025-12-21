"""
Logs block operations into database and lets players check history of any point on the map to easily detect griefing.

Requires sessions.py

Commands
^^^^^^^^

* ``/history`` Check block history with left-click. Right-click to check space directly above the block. Follow up clicks show older records

.. codeauthor:: Liza
"""

from datetime import datetime, timedelta, timezone
import os, sqlite3
from twisted.internet.task import LoopingCall
from piqueserver.commands import command, get_player
from piqueserver.config import config
from pyspades.bytes import ByteReader
from pyspades.common import coordinates, escape_control_codes, make_color
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from pyspades.contained import BlockAction, SetColor
from pyspades.packet import load_client_packet
from pyspades import contained as loaders

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
db_path_log = os.path.join(config.config_dir, 'blocklog.db')
con_log = sqlite3.connect(db_path_log)
cur_log = con_log.cursor()
cur_log.execute('CREATE TABLE IF NOT EXISTS blocklog(id INTEGER PRIMARY KEY, timestamp INTEGER, xyz INTEGER, session INTEGER, action INTEGER, color INTEGER, undone INTEGER)')
con_log.commit()
cur_log.close()

RESULTS_PER_PAGE = 6


ALL_SECTORS = [chr(x // 8 + ord('A')) + str(x % 8 + 1) for x in range(64)]

def get_sector(x, y):
    return chr(int(x // 64) + ord('A')) + str(int(y) // 64 + 1)


@command('history', 'h')
def history(connection):
    """
    Check block history with left-click. Right-click to check space directly above the block. Follow up clicks show older records
    /history
    """
    connection.history_mode = not connection.history_mode
    if connection.history_mode:
        return "History mode enabled"
    else:
        return "History mode disabled"

@command('inspect', 'i')
def inspect(connection, days=5, hours=0, sector=None):
    """
    Show the most active players in the sector in the last X days/hours
    /inspect <sector> <days> <hours>
    """
    if sector:
        sector = sector.upper()
        if sector not in ALL_SECTORS:
            return "Invalid sector. Example of a sector: A1"
    else:
        if connection.world_object:
            x, y, z = connection.get_location()
            sector = get_sector(x, y)
    sx, sy = coordinates(sector)
    time = datetime.now(timezone.utc) - timedelta(days=int(days), hours=int(hours))
    cur_log = con_log.cursor()
    actions = cur_log.execute('SELECT session, action FROM blocklog WHERE timestamp > ? AND (xyz >> 15) & 511 >= ? AND (xyz >> 15) & 511 < ? AND (xyz >> 6) & 511 >= ? AND (xyz >> 6) & 511 < ?', (
        int(time.timestamp()), sx, sx+64, sy, sy+64,)).fetchall()
    cur_log.close()
    sessions = list(set([x[0] for x in actions]))
    cur = con.cursor()
    players = [x[0] for x in cur.execute('SELECT user FROM sessions WHERE id IN (%s)' %
        ','.join('?'*len(sessions)), sessions).fetchall()]
    cur.close()
    players = {sessions[i]:players[i] for i in range(len(players))}
    stats = {}
    for session, action in actions:
        player = players[session]
        if player not in stats:
            stats[player] = [0, 0]
        if action:
            stats[player][1] += 1
        else:
            stats[player][0] -= 1
    if stats:
        connection.send_chat('=====')
        for player in [x[0] for x in sorted(stats.items(), key=lambda i: sum([abs(x) for x in i[1]]))][-6:]:
            broke, placed = stats[player]
            connection.send_chat("%s [\4%s\6/\5+%s\6] \0" % (player, broke, placed,))
    else:
        connection.send_chat('No recent history in the sector')

@command()
def blocks(connection, player=None):
    """
    Total amount of blocks placed by player
    /blocks <player>
    """
    if not player:
        player = connection.name
    else:
        player = ' '.join(player)
        if player.startswith('#'):
            player = connection.protocol.players[int(player[1:])].name
    cur = con.cursor()
    sessions = [x[0] for x in cur.execute('SELECT id FROM sessions WHERE user = ?', (player,)).fetchall()]
    cur.close()
    cur_log = con_log.cursor()
    block_count = cur_log.execute('SELECT COUNT(*) FROM blocklog WHERE action = 1 AND session IN (%s)' %
        ','.join('?'*len(sessions)), sessions).fetchone()[0]
    cur_log.close()
    return "%s placed %s blocks" % (player, f'{block_count:,}')


def apply_script(protocol, connection, config):
    class BlockLogConnection(connection):

        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.block_destroy_color = None
            self.block_destroy_spade_multiblock = False
            self.history_mode = False
            self.last_checked_block = None
            self.number_of_clicks = 0
            self.last_cast_ray_block = None

        def on_block_destroy(self, x, y, z, value):
            if self.history_mode:
                return False
            if connection.on_block_destroy(self, x, y, z, value) == False:
                return False
            if value == 2:
                self.block_destroy_color = (
                    self.protocol.world.map.get_color(x, y, z+1),
                    self.protocol.world.map.get_color(x, y, z),
                    self.protocol.world.map.get_color(x, y, z-1)
                    )
            else:
                self.block_destroy_color = self.protocol.world.map.get_color(x, y, z)

        def on_block_build_attempt(self, x, y, z):
            if self.history_mode:
                return False
            if connection.on_block_build_attempt(self, x, y, z) == False:
                return False

        def on_line_build_attempt(self, points):
            if self.history_mode:
                return False
            if connection.on_line_build_attempt(self, points) == False:
                return False

        def on_block_removed(self, x, y, z):
            if connection.on_block_removed(self, x, y, z) == False:
                return False
            if self.block_destroy_spade_multiblock:
                self.block_destroy_spade_multiblock = False
                return
            if self.block_destroy_color == None: # destroyed by grenade
                return
            if type(self.block_destroy_color[0]) == type(tuple()):
                self.block_destroy_spade_multiblock = True
                for i in range(3):
                    if self.block_destroy_color[i]:
                        xyz = x << 15 | y << 6 | z-(i-1)
                        r, g, b = self.block_destroy_color[i]
                        color = r << 16 | g << 8 | b
                        self.protocol.blocklog_queue += [(int(datetime.now(timezone.utc).timestamp()), xyz, self.session, False, color, False,)]
            elif type(self.block_destroy_color[0]) == type(int()):
                xyz = x << 15 | y << 6 | z
                r, g, b = self.block_destroy_color
                color = r << 16 | g << 8 | b
                self.protocol.blocklog_queue += [(int(datetime.now(timezone.utc).timestamp()), xyz, self.session, False, color, False,)]

        def on_block_build(self, x, y, z):
            if connection.on_block_build(self, x, y, z) == False:
                return False
            xyz = x << 15 | y << 6 | z
            r, g, b = self.color
            color = r << 16 | g << 8 | b
            timestamp = int(datetime.now(timezone.utc).timestamp())
            self.protocol.blocklog_queue = [None if (x[1] == xyz and x[3] == True) else x for x in self.protocol.blocklog_queue] # reduce repeating entries (e.g. from painting)
            self.protocol.blocklog_queue = [x for x in self.protocol.blocklog_queue if x]
            self.protocol.blocklog_queue += [(timestamp, xyz, self.session, True, color, False,)]

        def on_line_build(self, points):
            if connection.on_line_build(self, points) == False:
                return False
            for point in points:
                x, y, z = point
                xyz = x << 15 | y << 6 | z
                r, g, b = self.color
                color = r << 16 | g << 8 | b
                self.protocol.blocklog_queue += [(int(datetime.now(timezone.utc).timestamp()), xyz, self.session, True, color, False,)]

        def on_orientation_update(self, x, y, z):
            if self.history_mode:
                if self.world_object.cast_ray(8) != self.last_cast_ray_block:
                    self.last_cast_ray_block = self.world_object.cast_ray(8)
                    if self.last_cast_ray_block:
                        x, y, z = self.last_cast_ray_block
                        xyz = x << 15 | y << 6 | z
                        cur_log = con_log.cursor()
                        res = cur_log.execute('SELECT id, timestamp, xyz, session, action, color, undone FROM blocklog WHERE xyz = ? ORDER BY id DESC', (
                            xyz,)).fetchone()
                        cur_log.close()
                        if res:
                            action_id, timestamp, xyz, session, action, color, undone = res
                            cur = con.cursor()
                            self.send_cmsg("%s | %s | %s %s %s %s | %s | %s %s #%02X%02X%02X %s" % (
                                action_id,
                                datetime.fromtimestamp(timestamp).isoformat(sep=' ')[2:16],
                                (xyz >> 15) & 511,
                                (xyz >> 6) & 511,
                                xyz & 63,
                                chr(int(x // 64) + ord('A')) + str(y // 64 + 1),
                                session,
                                cur.execute('SELECT user FROM sessions WHERE id = ?', (session,)).fetchone()[0],
                                'placed' if action else 'broke',
                                (color >> 16) & 255, (color >> 8) & 255, color & 255,
                                '[rollbacked]' if undone else '',
                                ),
                                'Notice'
                            )
                            cur.close()
                        else:
                            self.send_cmsg("No history found for these coordinates", 'Notice')
            connection.on_orientation_update(self, x, y, z)

        def check_block_history(self, state, rightclick):
            if self.history_mode:
                if state == True:
                    coords = self.world_object.cast_ray(128)
                    if coords:
                        x, y, z = coords
                        if rightclick:
                            z = z - 1
                        xyz = x << 15 | y << 6 | z
                        if xyz != self.last_checked_block:
                            self.last_checked_block = xyz
                            self.number_of_clicks = 0
                        cur_log = con_log.cursor()
                        res = cur_log.execute('SELECT id, timestamp, xyz, session, action, color, undone FROM blocklog WHERE xyz = ? ORDER BY id DESC LIMIT ?, ?', (
                            xyz, self.number_of_clicks * RESULTS_PER_PAGE, (self.number_of_clicks + 1) * RESULTS_PER_PAGE)).fetchall()
                        cur_log.close()
                        if xyz == self.last_checked_block:
                            self.number_of_clicks += 1
                        if res:
                            res.reverse()
                            for i in res:
                                action_id, timestamp, xyz, session, action, color, undone = i
                                cur = con.cursor()
                                self.send_chat("%s | %s | %s %s %s %s | %s | %s %s #%02X%02X%02X %s \0" % (
                                    action_id,
                                    datetime.fromtimestamp(timestamp).isoformat(sep=' ')[2:16],
                                    (xyz >> 15) & 511,
                                    (xyz >> 6) & 511,
                                    xyz & 63,
                                    chr(int(x // 64) + ord('A')) + str(y // 64 + 1),
                                    session,
                                    cur.execute('SELECT user FROM sessions WHERE id = ?', (session,)).fetchone()[0],
                                    '\5placed\6' if action else '\4broke\6',
                                    (color >> 16) & 255, (color >> 8) & 255, color & 255,
                                    '[rollbacked]' if undone else '',
                                    )
                                )
                                cur.close()
                            self.send_chat("[Page %s]" % self.number_of_clicks)
                            if len(res) < RESULTS_PER_PAGE:
                                self.number_of_clicks = 0
                        else:
                            self.number_of_clicks = 0
                            self.send_chat("No history found for these coordinates")
                    else:
                        self.number_of_clicks = 0
                        self.send_chat("Click on a block to check its history")

        def on_shoot_set(self, state):
            self.check_block_history(state, False)
            connection.on_shoot_set(self, state)

        def on_secondary_fire_set(self, state):
            self.check_block_history(state, True)
            connection.on_secondary_fire_set(self, state)

        def on_disconnect(self):
            self.protocol.commit_blocklog_queue()
            connection.on_disconnect(self)

    class BlockLogProtocol(protocol):
        blocklog_queue = []
        blocklog_loop = None

        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.blocklog_loop = LoopingCall(self.commit_blocklog_queue)
            self.blocklog_loop.start(180)

        def commit_blocklog_queue(self):
            if self.blocklog_queue:
                cur_log = con_log.cursor()
                cur_log.executemany('INSERT INTO blocklog(timestamp, xyz, session, action, color, undone) VALUES(?, ?, ?, ?, ?, ?)', iter(self.blocklog_queue))
                con_log.commit()
                cur_log.close()
                self.blocklog_queue = []

    return BlockLogProtocol, BlockLogConnection
