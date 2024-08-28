"""
Logs block operations into database and lets players check history of any point on the map to easily detect griefing.

Requires sessions.py

Commands
^^^^^^^^

* ``/history`` Check block history with left-click. Right-click to check space directly above the block. Follow up clicks show older records

.. codeauthor:: Liza
"""

import datetime
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

results_per_page = 6

@command('history', 'h', 'i')
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

@command()
def blocks(connection, player=None):
    """
    Total amount of blocks placed by player
    /blocks <player>
    """
    if not player:
        player = connection.name
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
        block_destroy_color = None
        block_destroy_spade_multiblock = False
        history_mode = False
        last_checked_block = None
        number_of_clicks = 0
        last_cast_ray_block = None

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
                        self.protocol.blocklog_queue += [(int(datetime.datetime.now(datetime.timezone.utc).timestamp()), xyz, self.session, False, color, False,)]
            elif type(self.block_destroy_color[0]) == type(int()):
                xyz = x << 15 | y << 6 | z
                r, g, b = self.block_destroy_color
                color = r << 16 | g << 8 | b
                self.protocol.blocklog_queue += [(int(datetime.datetime.now(datetime.timezone.utc).timestamp()), xyz, self.session, False, color, False,)]

        def on_block_build(self, x, y, z):
            if connection.on_block_build(self, x, y, z) == False:
                return False
            xyz = x << 15 | y << 6 | z
            r, g, b = self.color
            color = r << 16 | g << 8 | b
            timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
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
                self.protocol.blocklog_queue += [(int(datetime.datetime.now(datetime.timezone.utc).timestamp()), xyz, self.session, True, color, False,)]

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
                                datetime.datetime.fromtimestamp(timestamp).isoformat(sep=' ')[2:16],
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
                            xyz, self.number_of_clicks * results_per_page, (self.number_of_clicks + 1) * results_per_page)).fetchall()
                        cur_log.close()
                        if xyz == self.last_checked_block:
                            self.number_of_clicks += 1
                        if res:
                            for i in res:
                                action_id, timestamp, xyz, session, action, color, undone = i
                                cur = con.cursor()
                                self.send_chat("%s | %s | %s %s %s %s | %s | %s %s #%02X%02X%02X %s \0" % (
                                    action_id,
                                    datetime.datetime.fromtimestamp(timestamp).isoformat(sep=' ')[2:16],
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
                            if len(res) < results_per_page:
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
