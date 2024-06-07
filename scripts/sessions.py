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
from piqueserver.commands import command, get_player
from piqueserver.config import config

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, dt, user COLLATE NOCASE, ip, client, logged_in)')
con.commit()
cur.close()


@command()
def name(self, victim, new_name):
    player = get_player(self.protocol, victim)
    old_name = player.name
    player.name = new_name
    return "%s is now known as %s" % (old_name, new_name)
# /name ic-liza 1

@command()
def seen(connection, player=None):
    """
    Shows the most recent date the player with that name joined
    /seen <player>
    """
    if not player:
        player = connection.name
    cur = con.cursor()
    res = cur.execute('SELECT dt, user FROM sessions WHERE user = ? ORDER BY id DESC LIMIT 1', (player,)).fetchone()
    cur.close()
    if res:
        dt, name = res
        return "Player named %s was seen on %s" % (name, dt[:10])
    else:
        return "No sessions found for this player"

@command()
def status(connection, player=None):
    """
    Show player's authorization status
    /status
    """
    if not player:
        player = connection.name
    if player.lower() not in [p.name.lower() for p in connection.protocol.players.values()]:
        return "Player not found"
    cur = con.cursor()
    session = cur.execute('SELECT user, logged_in FROM sessions WHERE user = ? ORDER BY id DESC LIMIT 1', (player,)).fetchone()
    record = cur.execute('SELECT user FROM users WHERE user = ?', (player,)).fetchone()
    cur.close()
    user, logged_in = session
    if record:
        connection.send_chat("%s is %slogged in" % (user, '' if logged_in else 'not '))
    else:
        connection.send_chat("%s is not registered" % user)

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
