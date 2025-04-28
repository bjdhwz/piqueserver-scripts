"""
1) Disables flag capture
2) Hides tents and intel from the map
3) Disables grenade damage
4) Infinite blocks
5) Fast travel command
6) Enables teamkill for Blue team and disables all killing for Green team, creating 'PVP' and 'Peace' teams

Commands
^^^^^^^^

* ``/flag <1|2> <hide>`` bring intel to your current location or hide it

.. codeauthor:: Liza
"""

import os
from piqueserver.commands import command, target_player
from piqueserver.config import config
from pyspades import contained as loaders
from pyspades.common import coordinates, make_color
from pyspades.constants import BLOCK_TOOL, BUILD_BLOCK, DESTROY_BLOCK, WEAPON_TOOL
from pyspades.contained import BlockAction, SetColor
from twisted.internet.task import LoopingCall

HIDE_POS = (-256, -256, 63)

ALL_SECTORS = [chr(x // 8 + ord('A')) + str(x % 8 + 1) for x in range(64)]

NOAUTOFLY = []

CHAIR_ENABLED = False # Creates a block under player on right-click while in the air

try:
    with open(os.path.join(config.config_dir, 'no_fly_list.txt')) as f:
        NOAUTOFLY = f.read().splitlines()
except:
    f = open(os.path.join(config.config_dir, 'no_fly_list.txt'), 'w')
    f.close()


def do_move(con, sector, silent=False, top=False):
    if not con.gt_cooldown:
        x, y = coordinates(sector)
        x += 32
        y += 32
        if top:
            for i in range(64):
                if con.protocol.map.get_solid(x, y, i):
                    z = i - 2
                    break
        else:
            z = con.protocol.map.get_height(x, y) - 2
        con.set_location((x-0.5, y-0.5, z))
        if not silent:
            con.protocol.broadcast_chat('%s teleported to %s' % (con.name, sector))
        if not con.admin:
            con.gt_loop = LoopingCall(con.gt_loop_check)
            con.gt_loop.start(10)
    else:
        con.send_chat("Please wait 10 seconds before teleporting again")

@command('gt', 'goto')
def gt(connection, sector):
    """
    Teleport to a sector
    /gt <sector>
    """
    if connection.quest_mode:
        return "This command is not available in quest sectors"
    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"
    do_move(connection, sector)

@command('gts', admin_only=True)
def gts(connection, sector):
    """
    Teleport to a sector silently
    /gts <sector>
    """
    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"
    do_move(connection, sector, True)

@command('gtop', 'go')
def gtop(connection, sector):
    """
    Teleport to a sector (always overground)
    /gtop <sector>
    """
    if connection.quest_mode:
        return "This command is not available in quest sectors"
    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"
    do_move(connection, sector, top=True)

@command('gtops', 'gos', admin_only=True)
def gtops(connection, sector):
    """
    Teleport to a sector silently (always overground)
    /gtops <sector>
    """
    sector = sector.upper()
    if sector not in ALL_SECTORS:
        return "Invalid sector. Example of a sector: A1"
    do_move(connection, sector, True, top=True)

@command('j', 'jump')
def jump(connection):
    """
    Teleport to where you're looking at
    /jump
    """
    if connection.team.id == 0:
        return 'Not available to PVP team'
    ray = connection.world_object.cast_ray(144)
    if ray:
        x, y, z = ray
        if x < 0:
            x += 512
        elif x > 511:
            x -= 512
        if y < 0:
            y += 512
        elif y > 511:
            y -= 512
        x = int(x)
        y = int(y)
        for i in range(64):
            if connection.protocol.map.get_solid(x, y, i):
                z = i - 2
                break
        connection.set_location((x, y, z))
    else:
        return "No block to jump to"

@command('f', 'fly')
def fly_shortcut(connection):
    """
    Enable flight
    /f
    """
    if connection.team == connection.protocol.team_1:
        return 'Not available to PVP team'
    else:
        connection.fly = not connection.fly
        message = 'now flying' if connection.fly else 'no longer flying'
        connection.send_chat("You're %s" % message)

@command()
@target_player
def unstick(connection, player):
    """
    Unstick yourself or another player and inform everyone on the server of it
    /unstick [player]
    """
    if player.name.lower() != connection.name.lower():
        if not connection.admin:
            return "You can't use this command on other players"
    connection.protocol.broadcast_chat("%s unstuck %s" %
                                  (connection.name, player.name), irc=True)
    player.set_location_safe(player.get_location())

@command(admin_only=True)
def flag(connection, team, hide=False):
    """
    Allows to use intel for decorative purposes
    /flag <1|2> <hide> - bring intel to your current location or hide it
    """
    if team == '1':
        flag = connection.protocol.team_1.flag
    elif team == '2':
        flag = connection.protocol.team_2.flag
    else:
        return "Usage: /flag <1|2> <hide>"

    if hide:
        flag.set(*HIDE_POS)
    else:
        x, y, z = [round(x*2)/2 for x in connection.get_location()]
        flag.set(x, y, z+2.5)
    flag.update()

@command(admin_only=True)
def tppos(connection, x, y, z):
    connection.set_location((int(x), int(y), int(z)))

@command()
def info(connection):
    """
    Display coordinates and color of the block that you're looking at
    /info
    """
    connection.info_mode = not connection.info_mode

@command()
def pingmon(con):
    """
    Monitor latency
    /pingmon
    """
    con.pingmon_mode = not con.pingmon_mode
    if con.pingmon_mode:
        con.latency_history = [0] * 30
        con.pingmon_loop = LoopingCall(con.update_pingmon)
        con.pingmon_loop.start(1)
    else:
        con.pingmon_loop.stop()

@command('clearammo', 'ca', admin_only=True)
@target_player
def clear_ammo(connection, player):
    """
    Remove player's ammo
    /clearammo
    """
    weapon_reload = loaders.WeaponReload()
    weapon_reload.player_id = player.player_id
    weapon_reload.clip_ammo = 0
    weapon_reload.reserve_ammo = 0
    player.grenades = 0
    player.weapon_object.reset()
    player.weapon_object.set_shoot(False)
    player.weapon_object.clip_ammo = 0
    player.weapon_object.reserve_ammo = 0
    player.send_contained(weapon_reload)
    return "%s's ammo has been cleared" % player.name

@command()
def autofly(connection):
    """
    Toggle auto-fly on join
    /autofly
    """
    if connection.name in NOAUTOFLY:
        NOAUTOFLY.remove(connection.name)
        connection.send_chat('Auto-fly has been enabled')
    else:
        NOAUTOFLY.append(connection.name)
        connection.send_chat('Auto-fly has been disabled')
    with open(os.path.join(config.config_dir, 'no_fly_list.txt'), 'w') as f:
        f.write('\n'.join(NOAUTOFLY))

@command('togglegrenadedamage', 'tgd', admin_only=True)
def toggle_grenade_damage(connection):
    connection.protocol.disable_grenade_damage = not connection.protocol.disable_grenade_damage
    if connection.protocol.disable_grenade_damage:
        connection.protocol.notify_admins('Grenade damage has been disabled')
    else:
        connection.protocol.notify_admins('Grenade damage has been enabled')


def apply_script(protocol, connection, config):
    class NoCaptureConnection(connection):

        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.info_mode = False
            self.info_cur = None
            self.pingmon_mode = False
            self.latency_history = [0] * 30
            self.gt_cooldown = False
            self.gt_loop = None
            self.quest_mode = False
            self.temp_block = None

        def update_pingmon(self):
            blocks = '▁▂▃▄▅▆▇█'
            if len(self.latency_history) == 30:
                self.latency_history = self.latency_history[1:]
            self.latency_history += [self.latency]
            l = self.latency_history
            base = min([x for x in l if x])
            mul = 7/(max(l)-base+1)
            l = [blocks[round((x-base)*mul)] if x else blocks[0] for x in l]
            self.send_cmsg(''.join(l) + ' ' + str(self.latency) + 'ms', 'Notice')

        def on_disconnect(self):
            try: # might already not exist when called
                self.pingmon_loop.stop()
            except:
                pass
            return connection.on_disconnect(self)

        def on_flag_take(self):
            return False

        def on_flag_drop(self):
            return False

        def on_flag_capture(self):
            return False

        def capture_flag(self):
            return False

        def on_team_join(self, team):
            if team == self.protocol.team_1:
                if self.fly:
                    self.fly = False
                    self.send_chat("You're no longer flying")
            elif team == self.protocol.team_2:
                if self.name not in NOAUTOFLY:
                    self.fly = True
            return team

        def on_login(self, name):
            connection.on_login(self, name)
            if self.admin:
                self.god = True
            if self.name in NOAUTOFLY:
                self.fly = False

        def on_block_destroy(self, x, y, z, value):
            if self.protocol.disable_grenade_damage:
                if value == 3:
                    return False
            if connection.on_block_destroy(self, x, y, z, value) == False:
                return False

        def on_block_build(self, x, y, z):
            self.refill()
            if connection.on_block_build(self, x, y, z) == False:
                return False

        def on_line_build(self, points):
            self.refill()
            if connection.on_line_build(self, points) == False:
                return False

        def on_hit(self, hit_amount, player, _type, grenade):
            if connection.on_hit(self, hit_amount, player, _type, grenade) == False:
                return False
            if self.team.id == 0:
                if player.team.id == 1:
                    return False
            if self.team.id == 1:
                return False

        def on_orientation_update(self, x, y, z):
            if self.info_mode:
                if self.world_object.cast_ray(128) != self.info_cur:
                    self.info_cur = self.world_object.cast_ray(128)
                    self.send_cmsg(str(self.info_cur) + ' #%02X%02X%02X ' % self.protocol.map.get_color(*self.info_cur) + str(self.protocol.map.get_color(*self.info_cur)), 'Notice')
            connection.on_orientation_update(self, x, y, z)

        def gt_loop_check(self):
            if self.gt_cooldown:
                self.gt_cooldown = False
                self.gt_loop.stop()
            else:
                self.gt_cooldown = True

        def on_disconnect(self):
            try: # might already not exist when called
                self.gt_cooldown.stop()
            except:
                pass
            return connection.on_disconnect(self)

        def on_secondary_fire_set(self, state):
            if state == True:
                x, y, z = self.get_location()
                if self.tool == BLOCK_TOOL and self.world_object.sneak:
                    ori = self.world_object.orientation
                    x += round(ori.x * 3)
                    y += round(ori.y * 3)
                    z += round(ori.z * 3)
                    if int(x) in range(512) and int(y) in range(512) and int(z) in range(64):
                        if connection.on_block_build_attempt(self, x, y, z) == False:
                            return
                        if not self.protocol.map.get_solid(x, y, z):
                            block_action = BlockAction()
                            block_action.player_id = self.player_id
                            block_action.x = x
                            block_action.y = y
                            block_action.z = z
                            block_action.value = BUILD_BLOCK
                            self.protocol.map.set_point(x, y, z, self.color)
                            self.protocol.broadcast_contained(block_action, save=True)
                            connection.on_block_build(self, int(x), int(y), int(z))
                if CHAIR_ENABLED:
                    z += 4 - int(self.world_object.crouch)
                    if int(x) in range(512) and int(y) in range(512) and int(z) in range(64):
                        if self.temp_block:
                            xt, yt, zt = self.temp_block
                            if int(x) != int(xt) or int(y) != int(yt) or int(z) < int(zt):
                                block_action = BlockAction()
                                block_action.player_id = 34
                                block_action.x = xt
                                block_action.y = yt
                                block_action.z = zt
                                block_action.value = DESTROY_BLOCK
                                self.send_contained(block_action)
                                self.temp_block = None
                                if z < 53 and not self.protocol.map.get_solid(x, y, z-1) and not self.protocol.map.get_solid(x, y, z) and not self.world_object.sneak and not self.tool == WEAPON_TOOL:
                                    self.temp_block = (x, y, z)
                                    block_action = BlockAction()
                                    block_action.player_id = 34
                                    block_action.x = x
                                    block_action.y = y
                                    block_action.z = z
                                    set_color = SetColor()
                                    set_color.player_id = 34
                                    set_color.value = make_color(255, 255, 255)
                                    self.protocol.broadcast_contained(set_color)
                                    block_action.value = BUILD_BLOCK
                                    self.send_contained(block_action)
                        else:
                            if z < 53 and not self.protocol.map.get_solid(x, y, z-1) and not self.protocol.map.get_solid(x, y, z) and not self.world_object.sneak and not self.tool == WEAPON_TOOL:
                                self.temp_block = (x, y, z)
                                block_action = BlockAction()
                                block_action.player_id = 34
                                block_action.x = x
                                block_action.y = y
                                block_action.z = z
                                set_color = SetColor()
                                set_color.player_id = 34
                                set_color.value = make_color(255, 255, 255)
                                self.protocol.broadcast_contained(set_color)
                                block_action.value = BUILD_BLOCK
                                self.send_contained(block_action)
            connection.on_secondary_fire_set(self, state)

    class NoCaptureProtocol(protocol):

        disable_grenade_damage = True

        def on_base_spawn(self, x, y, z, base, entity_id):
            return HIDE_POS

        def on_flag_spawn(self, x, y, z, flag, entity_id):
            return HIDE_POS

    return NoCaptureProtocol, NoCaptureConnection
