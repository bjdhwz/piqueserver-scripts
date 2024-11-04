"""
Same as vanilla /invisible, but doesn't kill player's avatar and adds /invstat to list all invisible players.

Commands
^^^^^^^^

* ``/invisible [player]``
* ``/invstat``

"""

from piqueserver.commands import command, target_player
from pyspades.common import make_color
from pyspades.contained import CreatePlayer, SetTool, KillAction, InputData, SetColor, WeaponInput


@command('invisible', 'invis', 'inv', admin_only=True)
@target_player
def invisible(connection, player):
    """
    Turn invisible
    /invisible [player]
    """
    protocol = connection.protocol
    player.invisible = not player.invisible
    player.filter_visibility_data = player.invisible
##    player.god = player.invisible
##    player.god_build = False
##    player.killing = not player.invisible
    if player.invisible:
        connection.protocol.notify_admins('%s became invisible' % connection.name)
##        kill_action = KillAction()
##        kill_action.kill_type = choice([GRENADE_KILL, FALL_KILL])
##        kill_action.player_id = kill_action.killer_id = player.player_id
##        reactor.callLater(1.0 / NETWORK_FPS, protocol.broadcast_contained,
##                          kill_action, sender=player)
    else:
        connection.protocol.notify_admins('%s became visible' % connection.name)
        x, y, z = player.world_object.position.get()
        create_player = CreatePlayer()
        create_player.player_id = player.player_id
        create_player.name = player.name
        create_player.x = x
        create_player.y = y
        create_player.z = z
        create_player.weapon = player.weapon
        create_player.team = player.team.id
        world_object = player.world_object
        input_data = InputData()
        input_data.player_id = player.player_id
        input_data.up = world_object.up
        input_data.down = world_object.down
        input_data.left = world_object.left
        input_data.right = world_object.right
        input_data.jump = world_object.jump
        input_data.crouch = world_object.crouch
        input_data.sneak = world_object.sneak
        input_data.sprint = world_object.sprint
        set_tool = SetTool()
        set_tool.player_id = player.player_id
        set_tool.value = player.tool
        set_color = SetColor()
        set_color.player_id = player.player_id
        set_color.value = make_color(*player.color)
        weapon_input = WeaponInput()
        weapon_input.primary = world_object.primary_fire
        weapon_input.secondary = world_object.secondary_fire
        protocol.broadcast_contained(create_player, sender=player, save=True)
        protocol.broadcast_contained(set_tool, sender=player)
        protocol.broadcast_contained(set_color, sender=player, save=True)
        protocol.broadcast_contained(input_data, sender=player)
        protocol.broadcast_contained(weapon_input, sender=player)
    if connection is not player and connection in protocol.players.values():
        if player.invisible:
            connection.protocol.notify_admins('%s made %s invisible' % (connection.name, player.name))
        else:
            connection.protocol.notify_admins('%s made %s visible' % (connection.name, player.name))

@command(admin_only=True)
def invstat(connection):
    """
    List invisible players
    /invstat
    """
    inv = []
    for player in connection.protocol.players.values():
        if player.invisible:
            inv += [player.name]
    if inv:
        return ', '.join(inv)
    else:
        return 'No invisible players'


def apply_script(protocol, connection, config):
    class InvisibleConnection(connection):

        def on_hit(self, hit_amount, player, _type, grenade):
            if connection.on_hit(self, hit_amount, player, _type, grenade) == False:
                return False
            if player.invisible:
                return False

    return protocol, InvisibleConnection
