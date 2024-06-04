"""
Makes player's chat messages and blocks invisible to other players. Player's avatar will appear AFK to others.

Commands
^^^^^^^^

* ``/shadowban <player>``

.. codeauthor:: Liza
"""

from piqueserver.commands import command, target_player
from pyspades.common import make_color
from pyspades import contained as loaders
from pyspades.contained import BlockAction, CreatePlayer, SetTool, KillAction, InputData, SetColor, WeaponInput
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK, NETWORK_FPS, WEAPON_KILL


@command('shadowban', 'sban', admin_only=True)
@target_player
def shadowban(connection, player):
    """
    Shadowban or unban a player
    /shadowban <player>
    """
    player.shadowbanned = not player.shadowbanned
    player.invisible = not player.invisible
    player.filter_visibility_data = player.invisible
    if player.shadowbanned:
        connection.protocol.notify_admins('%s has been shadowbanned by %s' % (player.name, connection.name))
    else:
        connection.protocol.notify_admins('%s has been unbanned from shadowban by %s' % (player.name, connection.name))
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
        connection.protocol.broadcast_contained(create_player, sender=player, save=True)
        connection.protocol.broadcast_contained(set_tool, sender=player)
        connection.protocol.broadcast_contained(set_color, sender=player, save=True)
        connection.protocol.broadcast_contained(input_data, sender=player)
        connection.protocol.broadcast_contained(weapon_input, sender=player)


def apply_script(protocol, connection, config):
    class ShadowbanConnection(connection):
        shadowbanned = False

        def on_block_destroy(self, x, y, z, value):
            if connection.on_block_destroy(self, x, y, z, value) == False:
                return False
            if self.shadowbanned:
                block_action = BlockAction()
                block_action.player_id = self.player_id
                block_action.value = DESTROY_BLOCK
                block_action.x = x
                block_action.y = y
                block_action.z = z
                self.protocol.broadcast_contained(block_action, rule=lambda p: p.name == self.name)
                return False

        def on_block_build_attempt(self, x, y, z):
            if connection.on_block_build_attempt(self, x, y, z) == False:
                return False
            if self.shadowbanned:
                block_action = BlockAction()
                block_action.player_id = self.player_id
                block_action.value = BUILD_BLOCK
                block_action.x = x
                block_action.y = y
                block_action.z = z
                self.protocol.broadcast_contained(block_action, rule=lambda p: p.name == self.name)
                return False

        def on_line_build_attempt(self, points):
            if connection.on_line_build_attempt(self, points) == False:
                return False
            if self.shadowbanned:
                for point in points:
                    block_action = BlockAction()
                    block_action.player_id = self.player_id
                    block_action.value = BUILD_BLOCK
                    block_action.x, block_action.y, block_action.z = point
                    self.protocol.broadcast_contained(block_action, rule=lambda p: p.name == self.name)
                return False

        def on_hit(self, hit_amount, player, _type, grenade):
            if connection.on_hit(self, hit_amount, player, _type, grenade) == False:
                return False
            if self.shadowbanned:
                return False
            if player.shadowbanned:
                return False

    return protocol, ShadowbanConnection
