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

from datetime import datetime
import os, sqlite3
from twisted.internet.task import LoopingCall
from piqueserver.commands import command, get_player
from piqueserver.config import config
from pyspades.common import escape_control_codes, coordinates

db_path = os.path.join(config.config_dir, 'sqlite.db')
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS signs(x, y, z, text)')
con.commit()
cur.close()


@command()
def sign(connection):
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


def apply_script(protocol, connection, config):
    class SignsConnection(connection):

        info_mode = False
        info_cur = None
        pingmon_mode = False
        latency_history = [0] * 30

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

    return protocol, SignsConnection
