"""
Logs block operations into database and lets players check history of any point on the map to easily detect griefing.

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
from pyspades.common import escape_control_codes, coordinates
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

results_per_page = 5

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


def apply_script(protocol, connection, config):
    class BlockLogConnection(connection):
        block_destroy_color = None
        block_destroy_spade_multiblock = False
        history_mode = False
        last_checked_block = None
        number_of_clicks = 0

        def on_block_destroy(self, x, y, z, value):
            if self.history_mode:
                return False
            if value == 2:
                self.block_destroy_color = (
                    self.protocol.world.map.get_color(x, y, z+1),
                    self.protocol.world.map.get_color(x, y, z),
                    self.protocol.world.map.get_color(x, y, z-1)
                    )
            else:
                self.block_destroy_color = self.protocol.world.map.get_color(x, y, z)
            if connection.on_block_destroy(self, x, y, z, value) == False:
                return False

        def on_block_build_attempt(self, x, y, z):
            if self.history_mode:
                return False
            if connection.on_block_build_attempt(self, x, y, z) == False:
                return False

        def on_line_build_attempt(self, points):
            if self.history_mode:
                return False
            for point in points:
                if connection.on_block_build_attempt(self, *point) == False:
                    return False

        def on_block_removed(self, x, y, z):
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
                        self.protocol.blocklog_queue += [(int(datetime.datetime.now(datetime.UTC).timestamp()), xyz, self.session, False, color, False,)]
            elif type(self.block_destroy_color[0]) == type(int()):
                xyz = x << 15 | y << 6 | z
                r, g, b = self.block_destroy_color
                color = r << 16 | g << 8 | b
                self.protocol.blocklog_queue += [(int(datetime.datetime.now(datetime.UTC).timestamp()), xyz, self.session, False, color, False,)]

        def on_block_build(self, x, y, z):
            xyz = x << 15 | y << 6 | z
            r, g, b = self.color
            color = r << 16 | g << 8 | b
            self.protocol.blocklog_queue += [(int(datetime.datetime.now(datetime.UTC).timestamp()), xyz, self.session, True, color, False,)]

        def on_line_build(self, points):
            for point in points:
                x, y, z = point
                xyz = x << 15 | y << 6 | z
                r, g, b = self.color
                color = r << 16 | g << 8 | b
                self.protocol.blocklog_queue += [(int(datetime.datetime.now(datetime.UTC).timestamp()), xyz, self.session, True, color, False,)]

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
                                self.send_chat("ID%s | %s | %s %s %s (%s) | %s | <%s> %s #%02X%02X%02X %s" % (
                                    action_id,
                                    datetime.datetime.fromtimestamp(timestamp).isoformat(sep=' ')[:19],
                                    (xyz >> 15) & 511,
                                    (xyz >> 6) & 511,
                                    xyz & 63,
                                    chr(int(x // 64) + ord('A')) + str(y // 64 + 1),
                                    session,
                                    cur.execute('SELECT user FROM sessions WHERE id = ?', (session,)).fetchone()[0],
                                    'placed' if action else 'broke',
                                    (color >> 16) & 255, (color >> 8) & 255, color & 255,
                                    '[rollbacked]' if undone else '',
                                    )
                                )
                                cur.close()
                            self.send_chat("[Page %s]" % self.number_of_clicks)
                            if len(res) < 5:
                                self.number_of_clicks = 0
                        else:
                            self.number_of_clicks = 0
                            self.send_chat("No history found for these coordinates")
                    else:
                        self.number_of_clicks = 0
                        self.send_chat("Click on a block to check its history")

        def on_shoot_set(self, state):
            self.check_block_history(state, False)

        def on_secondary_fire_set(self, state):
            self.check_block_history(state, True)

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
