"""
Cycle through different team colors. Colors are specified for Blue team. Green team gets inverse colors.

Commands
^^^^^^^^

* ``/teamcolordisco <interval> [#aabbcc #abc ...]`` - colors are random unless specified

.. codeauthor:: Liza
"""

import enet
from random import choice
from twisted.internet.task import LoopingCall
from piqueserver.commands import command
from pyspades import contained as loaders
from pyspades.color import interpolate_rgb


@command('bluecolor', 'team1color', 't1c', admin_only=True)
def team1_color(connection, r, g, b):
    connection.protocol.send_connection_data(team1_color = (int(r), int(g), int(b)))

@command('greencolor', 'team2color', 't2c', admin_only=True)
def team2_color(connection, r, g, b):
    connection.protocol.send_connection_data(team2_color = (int(r), int(g), int(b)))

@command('bluename', 'team1name', 't1n', admin_only=True)
def team1_name(connection, name):
    connection.protocol.send_connection_data(team1_name = name)

@command('greenname', 'team2name', 't2n', admin_only=True)
def team1_name(connection, name):
    connection.protocol.send_connection_data(team2_name = name)

def hex2rgb(h):
    h = h.strip('#')
    if len(h) == 3:
        h = ''.join([x*2 for x in h])
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

@command(admin_only=True)
def teamcolordisco(connection, interval=None, *colors):
    """
    Cycle through different team colors
    /teamcolordisco <interval> [#aabbcc #abc ...] - colors are random unless specified
    """
    if interval:
        if colors:
            if len(colors) < 2:
                return "Atleast two colors are required"
            colors = [hex2rgb(x) for x in colors]
            if float(interval) < 0.2:
                interval = 0.2
            connection.protocol.start_team_cycle(int(float(interval) * 10), colors)
        else:
            connection.protocol.start_team_cycle(int(float(interval) * 10), is_random=True)
    else:
        connection.protocol.stop_team_cycle()


def apply_script(protocol, connection, config):
    class TeamColorProtocol(protocol):

        is_team_active = False
        original_team_colors = (protocol.team1_color, protocol.team2_color)
        team_colors = []
        is_team_random = False
        team_interval = None
        team_n = 0

        def send_connection_data(self, team1_color = None, team2_color = None, team1_name = None, team2_name = None):
            if team1_color:
                self.team1_color = team1_color
                self.blue_team.color = team1_color
            if team2_color:
                self.team2_color = team2_color
                self.green_team.color = team2_color
            if team1_name:
                self.team1_name = team1_name
                self.blue_team.name = team1_name
            if team2_name:
                self.team2_name = team2_name
                self.green_team.name = team2_name

            for player in self.players.values():

                state_data = loaders.StateData()

                state_data.team1_color = self.team1_color
                if team1_color:
                    state_data.team1_color = team1_color

                state_data.team2_color = self.team2_color
                if team2_color:
                    state_data.team2_color = self.team2_color

                state_data.team1_name = self.team1_name
                if team1_name:
                    state_data.team1_name = team1_name

                state_data.team2_name = self.team2_name
                if team2_name:
                    state_data.team2_name = team2_name

                state_data.player_id = player.player_id
                state_data.fog_color = self.fog_color

                ctf_data = loaders.CTFState()
                ctf_data.cap_limit = self.max_score
                ctf_data.team1_score = self.blue_team.score
                ctf_data.team2_score = self.green_team.score

                ctf_data.team1_base_x = self.blue_team.base.x
                ctf_data.team1_base_y = self.blue_team.base.y
                ctf_data.team1_base_z = self.blue_team.base.z

                ctf_data.team2_base_x = self.green_team.base.x
                ctf_data.team2_base_y = self.green_team.base.y
                ctf_data.team2_base_z = self.green_team.base.z

                ctf_data.team1_has_intel = 0
                ctf_data.team2_flag_x = self.green_team.flag.x
                ctf_data.team2_flag_y = self.green_team.flag.y
                ctf_data.team2_flag_z = self.green_team.flag.z

                ctf_data.team2_has_intel = 0
                ctf_data.team1_flag_x = self.blue_team.flag.x
                ctf_data.team1_flag_y = self.blue_team.flag.y
                ctf_data.team1_flag_z = self.blue_team.flag.z

                state_data.state = ctf_data
                generated_data = state_data.generate()
                packet = enet.Packet(bytes(generated_data), enet.PACKET_FLAG_RELIABLE)
                player.peer.send(0, packet)

        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.team_loop = LoopingCall(self.update_team_color)

        def update_team_color(self):
            if self.is_team_random:
                if self.team_n % self.team_interval == 0:
                    self.team_colors = [self.team_colors[-1], (choice(range(255)), choice(range(255)), choice(range(255)))]
                clr = interpolate_rgb(self.team_colors[0], self.team_colors[1], self.team_n % self.team_interval / self.team_interval)
                self.send_connection_data(team1_color = clr)
                self.send_connection_data(team2_color = (255 - clr[0], 255 - clr[1], 255 - clr[2]))
            else:
                color_a = self.team_n % (len(self.team_colors) * self.team_interval) // self.team_interval
                color_b = (self.team_n + self.team_interval) % (len(self.team_colors) * self.team_interval) // self.team_interval
                clr = interpolate_rgb(self.team_colors[color_a], self.team_colors[color_b], self.team_n % self.team_interval / self.team_interval)
                self.send_connection_data(team1_color = clr)
                self.send_connection_data(team2_color = (255 - clr[0], 255 - clr[1], 255 - clr[2]))
            self.team_n += 1

        def start_team_cycle(self, interval, colors=[], is_random=False):
            if self.is_team_active:
                self.stop_team_cycle()
            self.is_team_active = True
            self.team_colors = colors
            self.is_team_random = is_random
            self.team_n = 0
            self.team_interval = interval
            self.team_colors = [
                (choice(range(255)), choice(range(255)), choice(range(255))),
                (choice(range(255)), choice(range(255)), choice(range(255)))
                ]
            self.team_loop.start(0.2)

        def stop_team_cycle(self):
            self.team_loop.stop()
            self.is_team_active = False
            self.send_connection_data(team1_color = self.original_team_colors[0])
            self.send_connection_data(team2_color = self.original_team_colors[1])

    return TeamColorProtocol, connection
