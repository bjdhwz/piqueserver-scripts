"""
Karma system. Allows players to vote with a comment for another player.

Requires auth.py

Commands
^^^^^^^^

* ``/karma <player>`` check player's karma
* ``/upvote <player> [comment]`` upvote player's karma
* ``/downvote <player> [comment]`` downvote player's karma
* ``/unvote <player>`` remove your vote
* ``/votes`` check your votes
* ``/karmatop`` show players with highest karma

.. codeauthor:: Liza
"""

import os, sqlite3
from piqueserver.commands import command
from piqueserver.config import config
from pyspades.common import escape_control_codes

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS karma(voter COLLATE NOCASE, receiver COLLATE NOCASE, value, comment)')
con.commit()
cur.close()


def vote(connection, value, receiver, *comment):
    if not connection.logged_in:
        return "Please log in using /login first"
    receiver = ' '.join(receiver)
    if receiver.startswith('#'):
        receiver = connection.protocol.players[int(receiver[1:])].name
    cur = con.cursor()
    vote = cur.execute('SELECT voter, receiver FROM karma WHERE voter = ? AND receiver = ?', (connection.name, receiver)).fetchall()
    cur.close()
    if len(vote) >= 1:
        return "You already voted for this player. Do /unvote if you want to remove existing vote"
    if connection.name.lower() == receiver.lower():
        return "Enter the name of the player you want to vote for"

    if comment:
        comment = '%s' % escape_control_codes(' '.join(comment[:200]))[:200]
    else:
        comment = ''
    cur = con.cursor()
    cur.execute('INSERT INTO karma(voter, receiver, value, comment) VALUES(?, ?, ?, ?)', (
        connection.name,
        receiver,
        value,
        comment))
    con.commit()
    cur.close()
    connection.protocol.notify_admins("%s voted %s %s" % (connection.name, value, receiver) + (" with a comment %s" % comment if comment else ''))
    return "You voted successfully"

@command('vote', 'upvote')
def upvote(connection, receiver, *comment):
    """
    Upvote player's karma
    /upvote <player> [comment]
    """
    return vote(connection, 1, receiver, *comment)

@command()
def downvote(connection, receiver, *comment):
    """
    Downvote player's karma
    /downvote <player> [comment]
    """
    return vote(connection, -1, receiver, *comment)

@command('unvote', 'removevote')
def unvote(connection, *receiver):
    """
    Remove your vote for player
    /unvote <player>
    """
    if not connection.logged_in:
        return "Please log in using /login first"
    receiver = ' '.join(receiver)
    if receiver.startswith('#'):
        receiver = connection.protocol.players[int(receiver[1:])].name
    cur = con.cursor()
    vote = cur.execute('SELECT voter, receiver FROM karma WHERE voter = ? AND receiver = ?', (connection.name, receiver)).fetchall()
    cur.close()
    if len(vote) < 1:
        return "You have no votes for %s" % receiver
    if connection.name.lower() == receiver.lower():
        return "Enter the name of the player"
    cur = con.cursor()
    cur.execute('DELETE FROM karma WHERE voter = ? AND receiver = ?', (
        connection.name,
        receiver))
    con.commit()
    cur.close()
    connection.protocol.notify_admins("%s removed vote for %s" % (connection.name, receiver))
    return "Vote removed"

@command()
def votes(connection):
    """
    Check your votes
    /votes
    """
    cur = con.cursor()
    votelist = cur.execute('SELECT value, receiver, comment FROM karma WHERE voter = ?', (connection.name,)).fetchall()
    cur.close()
    return '\n'.join(["[%s\6] <%s> %s \0" % ('\5+' + str(row[0]) if int(row[0]) > 0 else str(row[0]).replace('-', '\4-'), row[1], '"' + row[2] + '"' if row[2] else '') for row in votelist[-16:]])

@command()
def karma(connection, *player):
    """
    Check player's karma
    /karma <player>
    """
    name = connection.getplayer(*player)
    if name:
        cur = con.cursor()
        votes = cur.execute('SELECT value, comment FROM karma WHERE receiver = ?', (name,)).fetchall()
        cur.close()
    else:
        return "Player %s not found" % player
    if votes:
        votes = [_ for _ in reversed(votes[-16:])]
        for vote in votes:
            value, comment = vote
            connection.send_chat("[%s\6] %s \0" % ('\5+' + str(value) if int(value) > 0 else str(value).replace('-', '\4-'), comment))
        total = sum([x[0] for x in votes])
        connection.send_chat("%s's karma is %s\6 \0" % (name, '\5+' + str(total) if int(total) > 0 else str(total).replace('-', '\4-')))
    else:
        return "%s's karma is 0" % name

@command('karmatop', 'topkarma')
def karmatop(connection):
    """
    Show players with highest karma
    /karmatop
    """
    cur = con.cursor()
    top = cur.execute('SELECT SUM(value), receiver FROM karma GROUP BY receiver ORDER BY SUM(value) DESC LIMIT 6').fetchall()
    cur.close()
    return '\n'.join(["[%s\6] <%s> \0" % ('\5+' + str(player[0]) if player[0] > 0 else str(player[0]).replace('-', '\4-'), player[1]) for player in top])


def apply_script(protocol, connection, config):
    return protocol, connection
