"""
Creates effect of infinite and seamless map by teleporting players when they reach map edge.

.. codeauthor:: Liza
"""

from twisted.internet.task import LoopingCall


def apply_script(protocol, connection, config):
    class MapLoopConnection(connection):
        map_loop = None
        map_loop_timeout = 0
        map_loop_cycle = 2

        def map_border_check(self):
            x, y, z = self.get_location()
            if not self.map_loop_timeout:
                if x < 32 or x > 480 or y < 32 or y > 480:
                    if self.map_loop_cycle == 2:
                        self.map_loop_cycle = 0.03
                        self.map_loop_restart()
                else:
                    if self.map_loop_cycle == 0.03:
                        self.map_loop_cycle = 2
                        self.map_loop_restart()

                if x < 1:
                    z += 0.5
                    zc = z - int(self.world_object.crouch)
                    if self.protocol.map.get_solid(511, y, zc + 1):
                        z -= 1
                    if not self.protocol.map.get_solid(511, y, zc) and not self.protocol.map.get_solid(511, y, zc - 1):
                        self.set_location_safe((511.9, y - 0.5, z))
                        self.map_loop_timeout = 80

                if x > 510.9:
                    z += 0.5
                    zc = z - int(self.world_object.crouch)
                    if self.protocol.map.get_solid(0, y, zc + 1):
                        z -= 1
                    if not self.protocol.map.get_solid(0, y, zc) and not self.protocol.map.get_solid(0, y, zc - 1):
                        self.set_location_safe((-0.95, y - 0.5, z))
                        self.map_loop_timeout = 80

                if y < 1:
                    z += 0.5
                    zc = z - int(self.world_object.crouch)
                    if self.protocol.map.get_solid(x, 511, zc + 1):
                        z -= 1
                    if not self.protocol.map.get_solid(x, 511, zc) and not self.protocol.map.get_solid(x, 511, zc - 1):
                        self.set_location_safe((x - 0.5, 511.9, z))
                        self.map_loop_timeout = 80

                if y > 510.9:
                    z += 0.5
                    zc = z - int(self.world_object.crouch)
                    if self.protocol.map.get_solid(x, 0, zc + 1):
                        z -= 1
                    if not self.protocol.map.get_solid(x, 0, zc) and not self.protocol.map.get_solid(x, 0, zc - 1):
                        self.set_location_safe((x - 0.5, -0.95, z))
                        self.map_loop_timeout = 80

            else:
                self.map_loop_timeout -= 1

        def map_loop_restart(self):
            self.map_loop.stop()
            self.map_loop = LoopingCall(self.map_border_check)
            self.map_loop.start(self.map_loop_cycle)

        def on_spawn(self, pos):
            if not self.map_loop:
                self.map_loop = LoopingCall(self.map_border_check)
                self.map_loop.start(self.map_loop_cycle)
            return connection.on_spawn(self, pos)

        def on_disconnect(self):
            try: # might already not exist when called
                self.map_loop.stop()
            except:
                pass
            return connection.on_disconnect(self)

    return protocol, MapLoopConnection
