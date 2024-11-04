"""
Lets registered players claim 64x64 sectors of the map and share them with other players.

Requires auth.py

May conflict with building scripts (building scripts either don't work, or blocks in claimed sectors become breakable by anyone)
If that happens, try to change script loading order in config.

.. codeauthor:: Liza
"""

from datetime import datetime
import os, sqlite3
from twisted.internet.task import LoopingCall
from piqueserver.commands import command, get_player
from piqueserver.config import config
from pyspades.common import escape_control_codes, coordinates

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS claims(sector, owner COLLATE NOCASE, dt, name, mode)')
cur.execute('CREATE TABLE IF NOT EXISTS shared(sector, player COLLATE NOCASE, dt)')
cur.execute('CREATE TABLE IF NOT EXISTS signs(x, y, z, text)')
try:
    cur.execute('ALTER TABLE claims ADD mode')
except:
    pass
con.commit()
cur.close()

SECTORS_PER_PLAYER = 9


ALL_SECTORS = [chr(x // 8 + ord('A')) + str(x % 8 + 1) for x in range(64)]

def get_sector(x, y):
    return chr(int(x // 64) + ord('A')) + str(int(y) // 64 + 1)

def claimed_by(sector, name=None):
    cur = con.cursor()
    query = cur.execute('SELECT sector, owner FROM claims WHERE sector = ?', (sector,)).fetchone()
    cur.close()
    if query:
        sector, owner = query
        if owner:
            if name:
                if owner.lower() == name.lower():
                    return True
            return owner
        return None
    return False

@command()
def claim(connection, sector):
    """
    Claim a sector
    /claim <sector>
    """
    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"
    if not connection.logged_in:
        return "To claim a sector you have to log in first. Use /reg to register and /login to log in"
    owner = claimed_by(sector, connection.name)
    if owner == True:
        return "Sector %s is already claimed by you" % sector
    elif owner:
        return "Sector %s is already claimed. You can claim one of the /free sectors" % (sector, owner)
    elif owner == None:
        return "Sector %s is reserved and can't be claimed. You can claim one of the /free sectors" % sector
    else:
        cur = con.cursor()
        owned_by_player = cur.execute('SELECT sector FROM claims WHERE owner = ?', (connection.name,)).fetchall()
        cur.close()
        if owned_by_player:
            if len(owned_by_player) >= SECTORS_PER_PLAYER:
                return "You've reached the limit of claimed sectors. To claim another sector, you have to /unclaim one of your sectors first"
        cur = con.cursor()
        cur.execute('INSERT INTO claims(sector, owner, dt) VALUES(?, ?, ?)', (sector, connection.name, datetime.now().isoformat(sep=' ')[:16]))
        con.commit()
        cur.close()
        connection.protocol.notify_admins("%s claimed %s" % (connection.name, sector))
        return "Sector %s now belongs to you. Use /share to let other players build with you" % sector

@command()
def sector(connection, sector=None):
    """
    Get sector info
    /sector <sector>
    """
    if sector:
        sector = sector.upper()
        if sector not in ALL_SECTORS:
            return "Invalid sector. Example of a sector: A1"
    else:
        if connection.world_object:
            x, y, z = connection.get_location()
            sector = get_sector(x, y)

    owner = claimed_by(sector, connection.name)
    if owner == False:
        return "Sector %s is unclaimed" % sector
    if owner == True:
        owner = connection.name
    cur = con.cursor()
    dt, mode = cur.execute('SELECT dt, mode FROM claims WHERE sector = ?', (sector,)).fetchone()
    shared = cur.execute('SELECT player FROM shared WHERE sector = ?', (sector,)).fetchall()
    cur.close()
    status = ''
    if mode:
        status += 'in [%s] mode and ' % mode
    if owner == None: # reserved
        status += 'reserved'
    else:
        status += 'claimed by <%s> since %s' % (owner, dt[:10])
    if shared:
        return "Sector %s is %s and shared with %s" % (sector, status, ', '.join([x[0] for x in shared]))
    else:
        return "Sector %s is %s" % (sector, status)

@command()
def title(connection, sector, *name):
    """
    Add a name to sector that will be displayed as greeting message. Leave empty to remove the name
    /title <sector> <name>
    """
    if not connection.logged_in:
        return "Log in using /login to make changes to your claim"

    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"

    owner = claimed_by(sector, connection.name)
    if owner == True or connection.admin:
        if name:
            name = escape_control_codes(' '.join(name[:80]))[:80]
        else:
            name = ''
        cur = con.cursor()
        cur.execute('UPDATE claims SET name = ? WHERE sector = ?', (name, sector))
        con.commit()
        cur.close()
        connection.protocol.notify_admins("%s named %s \"%s\"" % (connection.name, sector, name))
        if name:
            return "Claim is now named %s" % name
        else:
            return "Claim no longer has a name"
    return "You can only name your claims"

@command()
def sign(connection, *text):
    """
    Add a message to the block you're looking at that'll be displayed when another player looks at this block. Leave empty to remove the message
    /sign <text>
    """
    if not connection.logged_in:
        return "Log in using /login to make changes to your claim"

    x, y, z = connection.world_object.cast_ray(12)
    owner = claimed_by(get_sector(x, y), connection.name)
    if owner == True or connection.admin:
        cur = con.cursor()
        if text:
            text = escape_control_codes(' '.join(text[:85]))[:85]
            res = cur.execute('SELECT text FROM signs WHERE x = ? AND y = ? AND z = ?', (x, y, z)).fetchone()
            if res:
                cur.execute('UPDATE signs SET text = ? WHERE x = ? AND y = ? AND z = ?', (text, x, y, z))
            else:
                cur.execute('INSERT INTO signs(x, y, z, text) VALUES(?, ?, ?, ?)', (x, y, z, text))
            connection.protocol.notify_admins("%s signed a block \"%s\"" % (connection.name, text))
        else:
            text = ''
            cur.execute('DELETE FROM signs WHERE x = ? AND y = ? AND z = ?', (x, y, z))
            connection.protocol.notify_admins("%s unsigned a block" % connection.name)
        con.commit()
        cur.close()
        if text:
            return "Block has been signed"
        else:
            return "Block is no longer signed"
    return "You can only sign blocks within your claim"

@command()
def claimed(connection, player=None):
    """
    List claimed sectors
    /claimed <player>
    """
    cur = con.cursor()
    if player:
        claimed_sectors = [x[0] + (' <' + x[1] + '>') for x in cur.execute('SELECT sector, owner FROM claims WHERE owner = ?', (player,)).fetchall()]
        if not claimed_sectors:
            return 'No sectors claimed by this player'
    else:
        claimed_sectors = [x[0] + (' <' + x[1] + '>' if x[1] else ' [reserved]') for x in cur.execute('SELECT sector, owner FROM claims').fetchall()]
    cur.close()
    return ', '.join(claimed_sectors)

@command('unclaimed', 'free')
def unclaimed(connection):
    """
    List unclaimed sectors
    /unclaimed
    """
    cur = con.cursor()
    claimed_sectors = [x[0] for x in cur.execute('SELECT sector FROM claims').fetchall()]
    unclaimed_sectors = [x for x in ALL_SECTORS if x not in claimed_sectors]
    cur.close()
    return ', '.join(unclaimed_sectors)

@command()
def unclaim(connection, sector):
    """
    Unclaim a sector and revert it back to public domain
    /unclaim <sector>
    """
    if not connection.logged_in:
        return "Log in using /login to make changes to your claim"

    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"

    owner = claimed_by(sector, connection.name)
    if owner == True or connection.admin:
        cur = con.cursor()
        cur.execute('DELETE FROM claims WHERE sector = ?', (sector,))
        cur.execute('DELETE FROM shared WHERE sector = ?', (sector,))
        con.commit()
        cur.close()
        connection.protocol.notify_admins("Sector %s has been unclaimed by %s" % (sector, connection.name))
        return "Sector %s has been unclaimed" % sector
    return "You can only unclaim your sectors"

@command()
def share(connection, sector, player):
    """
    Let other players build in a sector
    /share <sector> <player>
    """
    if not connection.logged_in:
        return "Log in using /login to make changes to your claim"

    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"

    owner = claimed_by(sector, connection.name)
    if not connection.admin:
        if owner != True:
            return "You can only share sectors you claim. Claim a sector using /claim first"

    if connection.name.lower() == player.lower():
        if not connection.admin:
            return "Enter the name of the player you want to let to build in that sector"

    cur = con.cursor()
    if cur.execute('SELECT player FROM shared WHERE sector = ? AND player = ?', (sector, player)).fetchone():
        cur.close()
        return "You've already shared that sector with this player. They have to /login to build"
    cur.close()

    cur = con.cursor()
    players_db = [x[0].lower() for x in cur.execute('SELECT user FROM users').fetchall()]
    players_online = [x.name.lower() for x in connection.protocol.players.values()]
    cur.close()

    if player.lower() in players_db:
        cur = con.cursor()
        cur.execute('INSERT INTO shared(sector, player, dt) VALUES(?, ?, ?)', (sector, player, datetime.now().isoformat(sep=' ')[:16]))
        con.commit()
        cur.close()
        if not get_player(connection.protocol, player).logged_in:
            connection.protocol.notify_player("Please /login to build there", player)
    elif player.lower() in players_online:
        p = get_player(connection.protocol, player)
        if not p.shared_sectors:
            p.shared_sectors = []
        p.shared_sectors += [sector]
    else:
        return "Player not found"

    connection.protocol.notify_player("You can now build in %s" % sector, player)
    connection.protocol.notify_admins("%s shared %s with %s" % (connection.name, sector, player))
    return "Player %s now can build in that sector" % player

@command()
def unshare(connection, sector, player):
    """
    Remove access to a sector for a player
    /unshare <sector> <player>
    """
    if not connection.logged_in:
        return "Log in using /login to make changes to your claim"

    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"

    owner = claimed_by(sector, connection.name)
    if not connection.admin:
        if owner != True:
            return "You can only manage sectors you claim. Claim a sector using /claim first"

    if connection.name.lower() == player.lower():
        if not connection.admin:
            return "Enter the name of the player"

    players_online = [x.name.lower() for x in connection.protocol.players.values()]
    if player.lower() in players_online:
        p = get_player(connection.protocol, player)
        if p.shared_sectors:
            p.shared_sectors = [x for x in p.shared_sectors if x != sector]

    cur = con.cursor()
    cur.execute('DELETE FROM shared WHERE sector = ? AND player = ?', (sector, player))
    con.commit()
    cur.close()

    connection.protocol.notify_player("You can no longer build in %s" % sector, player)
    connection.protocol.notify_admins("%s unshared %s for %s" % (connection.name, sector, player))
    return "Player %s no longer can build in that sector" % player

@command()
def public(connection, sector):
    """
    Toggle free building (for everyone) in a sector
    /public <sector>
    """
    if not connection.logged_in:
        return "Log in using /login to make changes to your claim"

    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"

    owner = claimed_by(sector, connection.name)
    if not connection.admin:
        if owner != True:
            return "You can only manage sectors you claim. Claim a sector using /claim first"

    owner = claimed_by(sector, connection.name)
    if owner == True or connection.admin:
        cur = con.cursor()
        mode = cur.execute('SELECT mode FROM claims WHERE sector = ?', (sector, )).fetchone()
        if mode:
            if mode[0] == 'public':
                cur.execute('UPDATE claims SET mode = ? WHERE sector = ?', (None, sector))
                con.commit()
                cur.close()
                connection.protocol.notify_admins("%s made %s private" % (connection.name, sector))
                return "Sector %s is no longer public" % sector
        cur.execute('UPDATE claims SET mode = ? WHERE sector = ?', ('public', sector))
        con.commit()
        cur.close()
        connection.protocol.notify_admins("%s made %s public" % (connection.name, sector))
        return "Sector %s is now public" % sector
    return "You can only manage sectors you claim. Claim a sector using /claim first"

@command()
def quest(connection, sector):
    """
    Toggle "adventure" mode (no building and no commands) in a sector
    /quest <sector>
    """
    if not connection.logged_in:
        return "Log in using /login to make changes to your claim"

    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"

    owner = claimed_by(sector, connection.name)
    if not connection.admin:
        if owner != True:
            return "You can only manage sectors you claim. Claim a sector using /claim first"

    owner = claimed_by(sector, connection.name)
    if owner == True or connection.admin:
        cur = con.cursor()
        mode = cur.execute('SELECT mode FROM claims WHERE sector = ?', (sector, )).fetchone()
        if mode:
            if mode[0] == 'quest':
                cur.execute('UPDATE claims SET mode = ? WHERE sector = ?', (None, sector))
                con.commit()
                cur.close()
                connection.protocol.notify_admins("%s unset %s from quest mode" % (connection.name, sector))
                return "Sector %s is no longer in quest mode" % sector
        cur.execute('UPDATE claims SET mode = ? WHERE sector = ?', ('quest', sector))
        con.commit()
        cur.close()
        connection.protocol.notify_admins("%s set %s into quest mode" % (connection.name, sector))
        return "Sector %s is now in quest mode" % sector
    return "You can only manage sectors you claim. Claim a sector using /claim first"

@command(admin_only=True)
def reserve(connection, sector):
    """
    Remove claim's owner
    /reserve <sector>
    """
    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"

    owner = claimed_by(sector)
    if owner:
        cur = con.cursor()
        cur.execute('UPDATE claims SET owner = ? WHERE sector = ?', (None, sector))
        cur.execute('INSERT INTO shared(sector, player, dt) VALUES(?, ?, ?)', (sector, owner, datetime.now().isoformat(sep=' ')[:16]))
        con.commit()
        cur.close()
        connection.protocol.notify_admins("Sector %s has been reserved by %s" % (sector, connection.name))
        return "Sector %s has been reserved" % sector
    elif owner == False:
        cur = con.cursor()
        cur.execute('INSERT INTO claims(sector, owner, dt) VALUES(?, ?, ?)', (sector, None, datetime.now().isoformat(sep=' ')[:16]))
        con.commit()
        cur.close()
        connection.protocol.notify_admins("Sector %s has been reserved by %s" % (sector, connection.name))
        return "Sector %s has been reserved" % sector
    elif owner == None:
        return "Sector %s is already reserved" % sector


def apply_script(protocol, connection, config):
    class ClaimsProtocol(protocol):

        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.sector_names_loop = LoopingCall(self.display_notifications)
            self.sector_names_loop.start(0.5)

        def display_notifications(self):
            for player in self.players.values():
                if not player.world_object:
                    return
                x, y, z = player.get_location()
                if player.current_sector != get_sector(x, y):
                    cur = con.cursor()
                    res = cur.execute('SELECT name, mode FROM claims WHERE sector = ?', (get_sector(x, y),)).fetchone()
                    cur.close()
                    if res:
                        name, mode = res
                        if name:
                            player.send_cmsg("Welcome to %s" % name, 'Status')
                        if mode == 'quest':
                            player.quest_mode = True
                        else:
                            player.quest_mode = False
                    player.current_sector = get_sector(x, y)
                ray = player.world_object.cast_ray(12)
                if ray:
                    if ray != player.last_cast_ray_block:
                        x, y, z = ray
                        cur = con.cursor()
                        text = cur.execute('SELECT text FROM signs WHERE x = ? AND y = ? AND z = ?', (x, y, z)).fetchone()
                        cur.close()
                        if text:
                            if text[0]:
                                player.current_sign = text[0]
                                player.send_cmsg(text[0], 'Notice')
                        else:
                            if player.current_sign:
                                player.current_sign = None
                                player.send_cmsg('\0', 'Notice')
                    else:
                        if player.current_sign:
                            player.send_cmsg(current_sign, 'Notice')
                else:
                    if player.current_sign:
                        player.current_sign = None
                        player.send_cmsg('\0', 'Notice')

        def is_claimed(self, x, y, z):
            cur = con.cursor()
            claimed = cur.execute('SELECT sector, owner, mode FROM claims').fetchall()
            cur.close()
            for sector, owner, mode in claimed:
                sx, sy = coordinates(sector)
                if x >= sx and y >= sy and x < sx + 64 and y < sy + 64:
                    cur = con.cursor()
                    shared = cur.execute('SELECT player FROM shared WHERE sector = ?', (sector,)).fetchall()
                    cur.close()
                    if shared:
                        shared = [x[0] for x in shared]
                    owners = [owner] + shared
                    return owners, mode
            return False, None

    class ClaimsConnection(connection):

        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.current_sector = None
            self.shared_sectors = None
            self.last_cast_ray_block = None
            self.current_sign = None
            self.quest_mode = False

        def can_build(self, x, y, z):
            if self.god:
                return True
            owners, mode = self.protocol.is_claimed(x, y, z)
            if owners:
                if self.logged_in:
                    if self.name.lower() in [x.lower() for x in owners if x]:
                        return True
                if self.shared_sectors:
                    if get_sector(x, y) in self.shared_sectors:
                        return True
                if mode == 'public':
                    return None # Same as unclaimed sectors
                if owners[0]:
                    self.send_chat("Sector %s is claimed. If you want to build here, ask %s to /share it with you. You can also build in /free sectors" % (get_sector(x, y), owners[0]))
                else:
                    self.send_chat("Sector %s is reserved" % get_sector(x, y))
                return False
            return None # Returned for unclaimed sectors

        def on_block_destroy(self, x, y, z, value):
            if connection.on_block_destroy(self, x, y, z, value) == False:
                return False
            if self.can_build(x, y, z) == False:
                return False

            if self.sculpting: # /sculpt
                if self.can_build(x, y, z) != True:
                    self.send_chat("Build commands can only be used in your sectors")
                    return False
            if self.state: # CBC compatibility. Limits usage to sectors players have access to
                if type(self.state).__name__ == 'GradientState': # exception
                    return
                if self.can_build(x, y, z) != True:
                    self.send_chat("Build commands can only be used in your sectors")
                    return False
                if '_choosing' in dir(self.state):
                    if self.state._choosing == 1:
                        if self.can_build(x, self.state._first_point.y, z) != True or self.can_build(self.state._first_point.x, y, z) != True:
                            self.send_chat("Build commands can only affect blocks within your sectors")
                            return False
                        if abs(x - self.state._first_point.x) > 64 or abs(y - self.state._first_point.y) > 64:
                            self.send_chat("Build commands are limited to 64 blocks")
                            return False

        def on_block_build_attempt(self, x, y, z):
            if connection.on_block_build_attempt(self, x, y, z) == False:
                return False
            if self.can_build(x, y, z) == False:
                return False

            if self.sculpting:
                if self.can_build(x, y, z) != True:
                    self.send_chat("Build commands can only be used in your sectors")
                    return False
            if self.state:
                if type(self.state).__name__ == 'GradientState':
                    return
                if self.can_build(x, y, z) != True:
                    self.send_chat("Build commands can only be used in your sectors")
                    return False
                if '_choosing' in dir(self.state):
                    if self.state._choosing == 1:
                        if self.can_build(x, self.state._first_point.y, z) != True or self.can_build(self.state._first_point.x, y, z) != True:
                            self.send_chat("Build commands can only affect blocks within your sectors")
                            return False
                        if abs(x - self.state._first_point.x) > 64 or abs(y - self.state._first_point.y) > 64:
                            self.send_chat("Build commands are limited to 64 blocks")
                            return False

        def on_line_build_attempt(self, points):
            if connection.on_line_build_attempt(self, points) == False:
                return False
            for point in points:
                if self.can_build(*point) == False:
                    return False

        def on_spawn(self, pos):
            self.protocol.sector_names_loop.stop()
            self.protocol.sector_names_loop = LoopingCall(self.protocol.display_notifications)
            self.protocol.sector_names_loop.start(0.5)
            return connection.on_spawn(self, pos)

    return ClaimsProtocol, ClaimsConnection
