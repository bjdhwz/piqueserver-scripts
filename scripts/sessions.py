"""
Log connections to assist in detecting ban circumvention and impersonation attempts.

.. codeauthor:: Liza
"""

from datetime import datetime
from collections import Counter
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
def seen(connection, *player):
    """
    Shows the most recent date the player with that name joined
    /seen <player>
    """
    if not player:
        player = connection.name
    player = ' '.join(player)
    cur = con.cursor()
    record = cur.execute('SELECT id, dt, user FROM sessions WHERE user LIKE ? ORDER BY id DESC LIMIT 1', ('%'+player+'%',)).fetchone()
    cur.close()
    if record:
        session_id, dt, name = record
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
def sessions(connection, *player):
    """
    Show recent sessions
    /sessions <player>
    """
    cur = con.cursor()
    if player:
        player = ' '.join(player)
        records = cur.execute('SELECT id, dt, ip, client, logged_in FROM sessions WHERE user = ? ORDER BY id DESC LIMIT 5', (player,)).fetchall()
    else:
        records = cur.execute('SELECT id, dt, ip, client, logged_in FROM sessions ORDER BY id DESC LIMIT 5').fetchall()
    cur.close()
    if records:
        for record in records:
            connection.send_chat("%s | %s | %s | %s | logged in: %s" % record)
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

@command(admin_only=True)
def recent(connection):
    """
    Show recent sessions
    /recent
    """
    active_sessions = [player.session for player in connection.protocol.players.values()]
    cur = con.cursor()
    records = cur.execute('SELECT id, dt, user, ip, client, logged_in FROM sessions ORDER BY id DESC LIMIT 5').fetchall()
    cur.close()
    if records:
        for record in records:
            connection.send_chat("%s | %s | %s | %s | %s | logged in: %s" % record)
    else:
        return "No recent sessions found"

@command(admin_only=True)
def same(connection, *player):
    """
    Show similar sessions
    /same <name>
    """
    cur = con.cursor()
    player = ' '.join(player)
    record = cur.execute('SELECT id, user, ip FROM sessions WHERE user = ? ORDER BY id DESC LIMIT 1', (player,)).fetchone()
    if record:
        session_id, user, current_ip = record
        ips = [x[0] for x in cur.execute('SELECT ip FROM sessions WHERE user = ?', (user,)).fetchall()]
        names = [x[0] for x in cur.execute('SELECT user FROM sessions WHERE ip = ?', (current_ip,)).fetchall()]
        othernames = []
        if len(set(ips)) > 1:
            for ip in set(ips):
                if ip != current_ip:
                    othernames += [(ip, x[0]) for x in cur.execute('SELECT user FROM sessions WHERE ip = ?', (ip,)).fetchall()]
        cur.close()
    else:
        cur.close()
        return "Player not found"

    ips_by_frequency = list(Counter(ips).most_common(len(set(ips))))
    if len(ips_by_frequency) > 5:
        connection.send_chat(', '.join(['<'+str(ip)+'>' for ip, freq in ips_by_frequency[5:]]))
    for ip, freq in reversed(ips_by_frequency[:5]):
        percent = round(freq/len(ips)*100)
        connection.send_chat('<%s> (%s/%s%%)' % (ip, freq, percent))
    connection.send_chat('IPs used with this name:')

    names_by_frequency = list(Counter(names).most_common(len(set(names))))
    if len(names_by_frequency) > 5:
        connection.send_chat(', '.join(['<'+str(name)+'>' for name, freq in names_by_frequency[5:]]))
    for name, freq in reversed(names_by_frequency[:5]):
        percent = round(freq/len(names)*100)
        connection.send_chat('<%s> (%s/%s%%)' % (name, freq, percent))
    connection.send_chat('Names used with this IP:')

    if othernames:
        othernames_by_frequency = list(Counter(othernames).most_common(len(set(othernames))))
        if len(names_by_frequency) > 5:
            connection.send_chat(', '.join([str(pair[0])+' <'+str(pair[1])+'>' for pair, freq in othernames_by_frequency[5:]]))
        for pair, freq in reversed(othernames_by_frequency[:5]):
            percent = round(freq/len(othernames)*100)
            connection.send_chat('%s <%s> (%s/%s%%)' % (pair[0], pair[1], freq, percent))
        connection.send_chat('Names used with IPs used by this name:')

@command(admin_only=True)
def sameip(connection, ip):
    """
    Show names used by IP
    /sameip <IP> - supports wildcard (eg 192.168.*)
    """
    cur = con.cursor()
    names = [x[0] for x in cur.execute('SELECT user FROM sessions WHERE ip LIKE ?', (ip.replace('*', '%'),)).fetchall()]
    cur.close()
    if names:
        names_by_frequency = list(Counter(names).most_common(len(set(names))))
        if len(names_by_frequency) > 5:
            connection.send_chat(', '.join(['<'+str(name)+'>' for name, freq in names_by_frequency[5:]]))
        for name, freq in reversed(names_by_frequency[:5]):
            percent = round(freq/len(names)*100)
            connection.send_chat('<%s> (%s/%s%%)' % (name, freq, percent))
        connection.send_chat('Names used with this IP:')
    else:
        return "No names found"


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
