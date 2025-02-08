from pyspades.contained import InputData
from twisted.internet.reactor import callLater, seconds
from piqueserver.commands import command

#script by MegaStar (27/10/2020)

input_data = InputData()
JETPACK = False #all players start with the jetpack on (default)


@command('jetpack', 'jp')
def jetpack(connection):
    connection.jetpack = False if connection.jetpack else True
    connection.send_chat('Your jetpack is turned {0}.'.format(['off', 'on'][int(connection.jetpack)]))


def apply_script(protocol, connection, config):
    class JetPackConnection(connection):
        def __init__(self, *args, **kwargs):
            self.jetpack = JETPACK
            connection.__init__(self, *args, **kwargs)

        def on_spawn(self, pos):
            if self.jetpack:
                self.jetpack = JETPACK
                self.send_chat('jetpack, press V to use it!')
            return connection.on_spawn(self, pos)

        def can_use_jetpack(self):
            if not self.world_object or not self.can_fly:
                return False
            return True

        def use_jetpack(self):
            if self.can_use_jetpack():
                self.world_object.jump = True
                input_data.player_id = self.player_id
                input_data.up = self.world_object.up
                input_data.down = self.world_object.down
                input_data.left = self.world_object.left
                input_data.right = self.world_object.right
                input_data.crouch = self.world_object.crouch
                input_data.sneak = self.world_object.sneak
                input_data.sprint = self.world_object.sprint
                input_data.jump = True
                self.protocol.send_contained(input_data)
                callLater(0.12, self.use_jetpack)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            if self.jetpack:
                if sneak:
                    self.can_fly = True;
                    self.use_jetpack()
                else:
                    self.can_fly = False;
            return connection.on_animation_update(self, jump, crouch, sneak, sprint)

    return protocol, JetPackConnection
