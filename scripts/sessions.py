"""
Log connections to assist in detecting ban circumvention and impersonation attempts.

.. codeauthor:: Liza
"""

from datetime import datetime
import os, sqlite3
from piqueserver.commands import command, get_player
from piqueserver.config import config

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, dt, user COLLATE NOCASE, ip, client, logged_in)')
con.commit()
cur.close()


##@command()
##@target_player
##def name(self, player, new_name):
##    old_name = player.name
##    player.name = new_name
##    return "%s is now known as %s" % (old_name, new_name)

@command()
def seen(connection, player=None):
    """
    Shows the most recent date the player with that name joined
    /seen <player>
    """
    if not player:
        player = connection.name
    cur = con.cursor()
    res = cur.execute('SELECT id, dt, user FROM sessions WHERE user = ? ORDER BY id DESC LIMIT 1', (player,)).fetchone()
    cur.close()
    if res:
        session_id, dt, name = res
        return "Player named %s was seen on %s%s" % (name, dt[:10], ' (ID%s)' % session_id if connection.admin else '')
    else:
        return "No sessions found for this player"

@command(admin_only=True)
def session(connection, session_id=None):
    """
    Inspect session by ID
    /session <ID>
    """
    if not session_id:
        session_id = connection.session
    cur = con.cursor()
    record = cur.execute('SELECT id, dt, user, ip, client, logged_in FROM sessions WHERE id = ?', (session_id,)).fetchone()
    cur.close()
    if record:
        return "%s | %s | %s | %s | %s | logged in: %s" % record
    else:
        return "Sessions not found"

@command(admin_only=True)
def sessions(connection, player=None):
    """
    Show recent sessions
    /sessions <player>
    """
    if not player:
        player = connection.name
    cur = con.cursor()
    records = cur.execute('SELECT id, dt, user, ip, client, logged_in FROM sessions ORDER BY id DESC LIMIT 5').fetchall()
    cur.close()
    if records:
        for record in records:
            connection.send_chat("%s | %s | %s | %s | %s | logged in: %s" % record)
    else:
        return "No sessions found for this player"

@command(admin_only=True)
def players(connection):
    """
    Show active sessions
    /players
    """
    active_sessions = [player.session for player in connection.protocol.players.values()]
    cur = con.cursor()
    records = cur.execute('SELECT id, dt, user, ip, client, logged_in FROM sessions WHERE id IN (%s)' % ','.join('?'*len(active_sessions)), active_sessions).fetchall()
    cur.close()
    if records:
        for record in records:
            connection.send_chat("%s | %s | %s | %s | %s | logged in: %s" % record)
    else:
        return "No active sessions found"


def apply_script(protocol, connection, config):
    class SessionsConnection(connection):
        session = None

        def on_login(self, name):
            cur = con.cursor()
            cur.execute('INSERT INTO sessions(dt, user, ip, client, logged_in) VALUES(?, ?, ?, ?, ?)', (datetime.now().isoformat(sep=' ')[:16], self.name, self.address[0], self.client_string, False))
            self.session = cur.lastrowid
            con.commit()
            cur.close()
            connection.on_login(self, name)

    return protocol, SessionsConnection
