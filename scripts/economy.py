"""
Money system. Allows players to send money to each other.
Every hour, each player online receives an amount of money equal to a total number of players online.

Commands
^^^^^^^^

* ``/pay <amount> <receiver> [comment]`` send money to another player
* ``/balance [player]`` check player's balance
* ``/balancetop`` show the richest players

.. codeauthor:: Liza
"""

from datetime import datetime
import os, sqlite3
from twisted.internet.task import LoopingCall
from piqueserver.commands import command, get_player, target_player
from piqueserver.config import config
from pyspades.common import escape_control_codes

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS wallets(user COLLATE NOCASE, balance INTEGER)')
cur.execute('CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY, dt, sender COLLATE NOCASE, sender_ip, sender_session, receiver COLLATE NOCASE, amount, comment, cancelled)')
con.commit()
cur.close()

S = '\4'


@command()
@target_player
def pay(connection, receiver, amount, *comment):
    """
    Send money to another player
    /pay <receiver> <amount> [comment] - amount should be a whole number
    """
    if not connection.logged_in:
        return "Please log in using /login first"
    cur = con.cursor()
    balance = cur.execute('SELECT balance FROM wallets WHERE user = ?', (connection.name,)).fetchone()
    cur.close()
    if not balance:
        return "Not enough money"
    try:
        amount = int(amount)
    except:
        return "Amount goes first and should be a whole number"
    if amount <= 0:
        return "Amount should be > 0"
    if balance[0] < amount:
        return "Not enough money"
    if connection.name.lower() == receiver.name.lower():
        return "Enter the name of the player you want to send money to"

    if comment:
        comment = '"%s"' % escape_control_codes(' '.join(comment[:80]))[:80]
    else:
        comment = ''
    cur = con.cursor()
    cur.execute('INSERT INTO transactions(dt, sender, sender_ip, sender_session, receiver, amount, comment, cancelled) VALUES(?, ?, ?, ?, ?, ?, ?, ?)', (
        datetime.now().isoformat(sep=' ')[:16],
        connection.name,
        connection.address[0],
        connection.session,
        receiver.name,
        amount,
        comment,
        False))
    cur.execute('UPDATE wallets SET balance = balance - ? WHERE user = ?', (amount, connection.name))
    cur.execute('INSERT INTO wallets(user, balance) VALUES(?, ?) ON CONFLICT(user) DO UPDATE SET balance = balance + excluded.balance', (receiver.name, amount))
    con.commit()
    cur.close()
    connection.protocol.notify_player("%s sent you %s%s %s" % (connection.name, amount, S, comment), receiver.name)
    connection.protocol.notify_admins("%s sent %s%s to %s %s" % (connection.name, amount, S, receiver.name, comment))
    return "Money have been sent"

@command('balance', 'bal', 'money')
def balance(connection, player=None):
    """
    Check player's balance
    /balance [player]
    """
    if not player:
        player = connection.name
    cur = con.cursor()
    balance = cur.execute('SELECT user, balance FROM wallets WHERE user LIKE ?', ('%'+player+'%',)).fetchone()
    cur.close()
    if not balance:
        balance = (player, '0')
    return "%s's balance is %s%s" % (balance[0], balance[1], S)

@command('balancetop', 'baltop', 'moneytop')
def balancetop(connection):
    """
    Show the richest players
    /balancetop
    """
    cur = con.cursor()
    top = cur.execute('SELECT user, balance FROM wallets ORDER BY balance DESC LIMIT 5').fetchall()
    cur.close()
    return '\n'.join(["%s%s%s" % (x[0].ljust(16), x[1], S) for x in top])

@command()
def transactions(connection, player=None):
    """
    Show latest transactions
    /transactions [player]
    """
    if not connection.logged_in:
        return "Please log in using /login first"
    if player.lower() != connection.name.lower():
        if not connection.admin:
            return "Can't show transactions of other players"
    else:
        player = connection.name
    cur = con.cursor()
    records = cur.execute('SELECT id, dt, sender, sender_ip, sender_session, receiver, amount, comment, cancelled FROM transactions WHERE sender = ? OR receiver = ? ORDER BY id DESC LIMIT 5', (player, player)).fetchall()
    cur.close()
    if records:
        if connection.admin:
            return '\n'.join(' '.join(records))
        else:
            return '\n'.join(["%s %s %s %s %s %s %s" % (x[0], x[1], x[2], x[5], x[6], x[7], x[8]) for x in records])
    else:
        return "No transactions for %s" % player

@command(admin_only=True)
def alltransactions(connection):
    """
    Show all recent transactions
    /alltransactions
    """
    cur = con.cursor()
    records = cur.execute('SELECT id, dt, sender, sender_ip, sender_session, receiver, amount, comment, cancelled FROM transactions ORDER BY id DESC LIMIT 5').fetchall()
    cur.close()
    if records:
        return '\n'.join(' '.join(records))
    else:
        return "No transactions yet"

@command(admin_only=True)
def transaction(connection, transaction_id):
    """
    Show details about transaction
    /transaction <id>
    """
    cur = con.cursor()
    records = cur.execute('SELECT * FROM transactions WHERE id = ?', (transaction_id)).fetchone()
    cur.close()
    return ' '.join(records)

@command(admin_only=True)
def refund(connection, transaction_id):
    """
    Cancel transaction and refund sender
    /refund <id>
    """
    cur = con.cursor()
    if cur.execute('SELECT sender, receiver, amount FROM transactions WHERE id = ?', (transaction_id)).fetchone()[0]:
        cur.execute('UPDATE transactions SET cancelled = ? WHERE id = ?', (datetime.now().isoformat(sep=' ')[:16], transaction_id))
        cur.execute('UPDATE wallets SET balance = balance + ? WHERE user = ?', (amount, sender))
        cur.execute('UPDATE wallets SET balance = balance - ? WHERE user = ?', (amount, receiver))
        con.commit()
        cur.close()
        return "Transaction cancelled, %s%s returned to %s from %s" % (amount, S, sender, receiver)
    else:
        cur.close()
        return "No transaction with id %s" % transaction_id


def apply_script(protocol, connection, config):
    class EconomyProtocol(protocol):

        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.economy_loop = LoopingCall(self.give_money_bonus)
            self.economy_loop.start(60)

        def give_money_bonus(self):
            if datetime.now().minute == 0:
                amount = len(self.players.values())
                for player in self.players.values():
                    cur = con.cursor()
                    cur.execute('INSERT INTO wallets(user, balance) VALUES(?, ?) ON CONFLICT(user) DO UPDATE SET balance = balance + excluded.balance', (player.name, amount))
                    con.commit()
                    cur.close()
                    player.send_chat("%s%s have been added to your account. Use /balance to check your balance" % (amount, S))

    return EconomyProtocol, connection
