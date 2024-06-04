"""
Log connections to assist in detecting ban circumvention and impersonation attempts.

Commands
^^^^^^^^

* ``/send <amount> <receiver> [comment]`` send money to another player
* ``/balance [player]`` check player's balance
* ``/balancetop`` show the richest players

.. codeauthor:: Liza
"""

from datetime import datetime
import os, sqlite3
from piqueserver.commands import command
from piqueserver.config import config

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, dt, user, ip, client, logged_in)')


@command()
def seen(connection, player=None):
    """
    Shows the most recent date the player with that name joined
    /seen <player>
    """
    if not player:
        player = connection.name
    q = cur.execute('SELECT dt, user FROM sessions WHERE user = ? ORDER BY id DESC LIMIT 1 COLLATE NOCASE', (player,)).fetchone()
    if q:
        dt, name = q
        return "Player named %s was seen on %s" % (name, dt[:10])
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
    log = cur.execute('SELECT id, dt, user, ip, client, logged_in FROM sessions WHERE id = ?', (session_id,)).fetchone()
    if log:
        return "%s | %s | %s | %s | %s | logged in: %s" % log
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
    log = cur.execute('SELECT id, dt, user, ip, client, logged_in FROM sessions ORDER BY id DESC LIMIT 5').fetchall()
    if log:
        for session in log:
            connection.send_chat("%s | %s | %s | %s | %s | logged in: %s" % session)
    else:
        return "No sessions found for this player"

@command(admin_only=True)
def players(connection):
    """
    Show active sessions
    /players
    """
    active_sessions = [player.session for player in connection.protocol.players.values()]
    log = cur.execute('SELECT id, dt, user, ip, client, logged_in FROM sessions WHERE id IN (%s)' % ','.join('?'*len(active_sessions)), active_sessions).fetchall()
    if log:
        for session in log:
            connection.send_chat("%s | %s | %s | %s | %s | logged in: %s" % session)
    else:
        return "No active sessions found"


def apply_script(protocol, connection, config):
    class SessionsConnection(connection):
        session = None

        def on_login(self, name):
            connection.on_login(self, name)
            cur.execute('INSERT INTO sessions(dt, user, ip, client, logged_in) VALUES(?, ?, ?, ?, ?)', (datetime.now().isoformat(sep=' ')[:16], self.name, self.address[0], self.client_string, False))
            self.session = cur.lastrowid
            con.commit()

    return protocol, SessionsConnection
