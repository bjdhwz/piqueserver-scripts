"""
Lets registered players claim 64x64 sectors of the map and share them with other players.

Requires auth.py

May conflict with building scripts (building scripts either don't work, or blocks in claimed sectors become breakable by anyone)
paint.py, sculpt.py and other scripts in this repo are edited for compatibility.

.. codeauthor:: Liza
"""

from datetime import datetime
import os, random, sqlite3
from twisted.internet.task import LoopingCall
from piqueserver.commands import command, get_player
from piqueserver.config import config
from pyspades.color import interpolate_rgb
from pyspades.common import escape_control_codes, coordinates, make_color
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from pyspades.contained import BlockAction, FogColor, SetColor

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS claims(sector, owner COLLATE NOCASE, dt, name, mode, fog)')
cur.execute('CREATE TABLE IF NOT EXISTS shared(sector, player COLLATE NOCASE, dt)')
cur.execute('CREATE TABLE IF NOT EXISTS signs(x, y, z, text)')
con.commit()
cur.close()

SECTORS_PER_PLAYER = 5

cur = con.cursor()
SIGNS = cur.execute('SELECT x, y, z FROM signs').fetchall()
cur.close()


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

def hex2rgb(h):
    h = h.strip('#')
    if len(h) == 3:
        h = ''.join([x*2 for x in h])
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


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
        return "Sector %s is already claimed. You can claim one of the /free sectors" % sector
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
    has_access = connection.can_build(x, y, z)
    if has_access == True or connection.admin:
        cur = con.cursor()
        if text:
            text = escape_control_codes(' '.join(text[:85]))[:85]
            res = cur.execute('SELECT text FROM signs WHERE x = ? AND y = ? AND z = ?', (x, y, z)).fetchone()
            if res:
                cur.execute('UPDATE signs SET text = ? WHERE x = ? AND y = ? AND z = ?', (text, x, y, z))
            else:
                cur.execute('INSERT INTO signs(x, y, z, text) VALUES(?, ?, ?, ?)', (x, y, z, text))
            SIGNS.append((x, y, z))
            connection.protocol.notify_admins("%s signed a block \"%s\"" % (connection.name, text))
        else:
            text = ''
            cur.execute('DELETE FROM signs WHERE x = ? AND y = ? AND z = ?', (x, y, z))
            SIGNS.remove((x, y, z))
            connection.protocol.notify_admins("%s unsigned a block" % connection.name)
        con.commit()
        cur.close()
        if text:
            return "Block has been signed"
        else:
            return "Block is no longer signed"
    return "You can only sign blocks within your claim"

@command('claimed', 'owned', 'shared')
def owned(connection, *player):
    """
    List owned sectors
    /owned <player>
    """
    cur = con.cursor()
    if player:
        player = ' '.join(player)
        shared_sectors = cur.execute('SELECT sector FROM shared WHERE player = ?', (player,)).fetchall()
        if shared_sectors:
            connection.send_chat("Shared: " + ', '.join([x[0] for x in shared_sectors]))
        else:
            connection.send_chat('Shared: none')
        claimed_sectors = cur.execute('SELECT sector FROM claims WHERE owner = ?', (player,)).fetchall()
        if claimed_sectors:
            connection.send_chat("Claimed: " + ', '.join([x[0] for x in claimed_sectors]))
        else:
            connection.send_chat('Claimed: none')
    else:
        claimed_sectors = [x[0] + (' <' + x[1] + '>' if x[1] else ' [reserved]') for x in cur.execute('SELECT sector, owner FROM claims').fetchall()]
        if claimed_sectors:
            connection.send_chat(', '.join(claimed_sectors))
        else:
            connection.send_chat('No claimed sectors')
    cur.close()

@command()
def my(connection):
    """
    List sectors you claim or which were shared with you
    /my
    """
    cur = con.cursor()
    shared_sectors = cur.execute('SELECT sector FROM shared WHERE player = ?', (connection.name,)).fetchall()
    if shared_sectors:
        connection.send_chat("Shared: " + ', '.join([x[0] for x in shared_sectors]))
    else:
        connection.send_chat('Shared: none')
    claimed_sectors = cur.execute('SELECT sector FROM claims WHERE owner = ?', (connection.name,)).fetchall()
    if claimed_sectors:
        connection.send_chat("Claimed: " + ', '.join([x[0] for x in claimed_sectors]))
    else:
        connection.send_chat('Claimed: none')
    cur.close()

@command('unclaimed', 'free')
def unclaimed(connection, *args):
    """
    List unclaimed and public sectors
    /free
    """
    cur = con.cursor()
    claimed_sectors = [x[0] for x in cur.execute('SELECT sector FROM claims').fetchall()]
    unclaimed_sectors = [x for x in ALL_SECTORS if x not in claimed_sectors]
    public_sectors = [x[0] for x in cur.execute('SELECT sector FROM claims WHERE mode = "public"').fetchall()]
    cur.close()
    if unclaimed_sectors:
        connection.send_chat("Unclaimed: " + ', '.join(unclaimed_sectors))
    else:
        connection.send_chat("Unclaimed: currently none :(")
    if public_sectors:
        connection.send_chat("Free build: " + ', '.join(public_sectors))

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
def share(connection, sector, *player):
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

    player = ' '.join(player)
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
def unshare(connection, sector, *player):
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

    player = ' '.join(player)
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
    if owner == False:
        return "You can only set mode to a claimed sector. Claim a sector using /claim first"
    if owner != True and not connection.admin:
        return "You can only manage sectors you claim. Claim a sector using /claim first"

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
    if owner == False:
        return "You can only set mode to a claimed sector. Claim a sector using /claim first"
    if owner != True and not connection.admin:
        return "You can only manage sectors you claim. Claim a sector using /claim first"

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

@command()
def setfog(connection, sector, *color):
    """
    Set fog color in a sector
    /setfog <sector> <color> - supports rgb/hex values. Leave empty to reset.
    """
    if not connection.logged_in:
        return "Log in using /login to make changes to your claim"

    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"

    if color:
        if color[0] == '?':
            cur = con.cursor()
            cur.execute('UPDATE claims SET fog = ? WHERE sector = ?', ('#%02X%02X%02X ' % color, sector))
            con.commit()
            cur.close()
            return str(connection.protocol.fog_color)

    owner = claimed_by(sector, connection.name)

    if owner == True or connection.admin:
        if color:
            if (len(color) == 3):
                r = int(color[0])
                g = int(color[1])
                b = int(color[2])
                color = (r, g, b)
            elif (len(color) == 1 and color[0][0] == '#'):
                color = hex2rgb(color[0])
            elif color[0] == 'default':
                color = (128, 232, 255)
            else:
                color = None
        else:
            color = None
        cur = con.cursor()
        if color:
            cur.execute('UPDATE claims SET fog = ? WHERE sector = ?', ('#%02X%02X%02X ' % color, sector))
            connection.protocol.notify_admins("%s set fog color in %s to %s" % (connection.name, sector, str(color)))
        else:
            cur.execute('UPDATE claims SET fog = ? WHERE sector = ?', (None, sector))
            connection.protocol.notify_admins("%s removed fog color in %s" % (connection.name, sector))
        con.commit()
        cur.close()
        return "Claim fog color updated"
    return "You can only manage sectors you claim. Claim a sector using /claim first"

def build(con, x, y, z, color=None):
    block_action = BlockAction()
    block_action.player_id = 32
    block_action.x = x
    block_action.y = y
    block_action.z = z
    if color:
        set_color = SetColor()
        set_color.player_id = 32
        set_color.value = make_color(*color)
        con.send_contained(set_color)
        block_action.value = BUILD_BLOCK
    else:
        block_action.value = DESTROY_BLOCK
    con.send_contained(block_action)

@command(admin_only=True)
def fixnameloop(connection):
    """
    Debug command to restart loop
    /fixnameloop
    """
    try:
        connection.protocol.sector_names_loop.stop()
        connection.protocol.sector_names_loop.start(connection.protocol.sector_names_interval)
    except:
        pass


def apply_script(protocol, connection, config):
    class ClaimsProtocol(protocol):

        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.sector_names_interval = 0.2
            self.sector_names_loop = LoopingCall(self.display_notifications)
            self.sector_names_loop.start(self.sector_names_interval)

        def display_notifications(self):
            for player in self.players.values():
                if not player.world_object:
                    return
                x, y, z = player.get_location()
                if player.current_sector != get_sector(x, y):
                    cur = con.cursor()
                    res = cur.execute('SELECT name, mode, fog FROM claims WHERE sector = ?', (get_sector(x, y),)).fetchone()
                    cur.close()
                    fog = tuple(self.fog_color)
                    player.quest_mode = False
                    if res:
                        name, mode, fog_db = res
                        if fog_db:
                            fog = hex2rgb(fog_db)
                        if name:
                            player.send_cmsg("Welcome to %s" % name, 'Status')
                        if mode == 'quest':
                            player.quest_mode = True
                    player.sector_fog_transition(fog)
                    player.current_sector = get_sector(x, y)
                block = player.world_object.cast_ray(32)
                if block:
                    block = tuple(block)
                if block in SIGNS:
                    if player.current_sign:
                        text, color, sign_block = player.current_sign
                        if block == sign_block:
                            player.send_cmsg(text, 'Notice')
                            return
                        else:
                            text, color, sign_block = player.current_sign
                            build(player, *sign_block, color)
                            player.current_sign = None
                            player.send_cmsg('\0', 'Notice')
                    x, y, z = block
                    cur = con.cursor()
                    text = cur.execute('SELECT text FROM signs WHERE x = ? AND y = ? AND z = ?', (x, y, z)).fetchone()
                    cur.close()
                    if text:
                        player.current_sign = (text[0], self.world.map.get_color(x, y, z), block)
                        player.send_cmsg(text[0], 'Notice')
                        build(player, x, y, z, None)
                        build(player, x, y, z, (255, 255, 0))
                else:
                    if player.current_sign:
                        text, color, sign_block = player.current_sign
                        build(player, *sign_block, color)
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
            self.current_sign = None
            self.quest_mode = False
            self.sfog_a = self.protocol.fog_color
            self.sfog_b = None
            self.sfog_step = None
            self.sfog_loop = None

        def sector_fog_transition(self, color):
            if self.sfog_loop:
                self.sfog_loop.stop()
            self.sfog_b = color
            self.sfog_step = 1
            self.sfog_loop = LoopingCall(self.update_sector_fog)
            self.sfog_loop.start(0.05)

        def update_sector_fog(self):
            sfog_color = FogColor()
            self.sfog_a = interpolate_rgb(self.sfog_a, self.sfog_b, self.sfog_step / 64)
            sfog_color.color = make_color(*self.sfog_a)
            self.send_contained(sfog_color)
            if self.sfog_step == 64:
                self.sfog_step = None
                self.sfog_loop.stop()
                self.sfog_loop = None
            else:
                self.sfog_step += 1

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
            self.protocol.sector_names_loop.start(self.protocol.sector_names_interval)
            return connection.on_spawn(self, pos)

        def get_spawn_location(self):
            try:
                if self.current_sector:
                    spawn_sector = self.current_sector
                else:
                    cur = con.cursor()
                    my_sectors = [x[0] for x in cur.execute('SELECT sector FROM claims WHERE owner = ?', (self.name,)).fetchall()]
                    if my_sectors:
                        spawn_sector = random.choice(my_sectors)
                    else:
                        shared_sectors = [x[0] for x in cur.execute('SELECT sector FROM shared WHERE player = ?', (self.name,)).fetchall()]
                        if shared_sectors:
                            spawn_sector = random.choice(shared_sectors)
                        else:
                            claimed_sectors = [x[0] for x in cur.execute('SELECT sector FROM claims').fetchall()]
                            unclaimed_sectors = [x for x in ALL_SECTORS if x not in claimed_sectors]
                            if unclaimed_sectors:
                                spawn_sector = random.choice(unclaimed_sectors)
                            else:
                                public_sectors = [x[0] for x in cur.execute('SELECT sector FROM claims WHERE mode = "public"').fetchall()]
                                if public_sectors:
                                    spawn_sector = random.choice(public_sectors)
                                else:
                                    spawn_sector = random.choice(ALL_SECTORS)
                    cur.close()
            except:
                spawn_sector = random.choice(ALL_SECTORS)

            sx, sy = coordinates(spawn_sector)
            sx += random.choice(range(64))
            sy += random.choice(range(64))
            sz = self.protocol.map.get_z(sx, sy)
            return (sx, sy, sz)

    return ClaimsProtocol, ClaimsConnection
