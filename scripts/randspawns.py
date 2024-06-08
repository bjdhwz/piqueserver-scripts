"""
.. codeauthor:: sByte
"""

from piqueserver.commands import command
from random import randint

@command("setspawn")
def setspawn(p, *args):
	if not p or not p.world_object:
		return "You need to join in a team to use this command."

	if p.custom_spawn:
		p.custom_spawn = None
		return "You will start spawning randomly in the map."
	else:
		x,y,z = p.world_object.position.get()
		p.custom_spawn = (x,y,z)

		return "You will spawn on %i, %i, %i in next death!"%(x,y,z)

def apply_script(protocol, connection, config):
	class randConnec(connection):
		custom_spawn = None

		def get_spawn_location(self):
			if self.custom_spawn:
				return self.custom_spawn

			x = randint(0, 511)
			y = randint(0, 511)
			z = self.protocol.map.get_z(x,y)

			return (x,y,z)

	return protocol, randConnec
