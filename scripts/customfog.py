"""
Cycle through different fog colors
Photosensitivity warning! Please exercise caution with contrast colors, especially if loop interval is under 1s

Commands
^^^^^^^^

* ``/customdisco <interval [#aabbcc #abc ...]`` cycle through specified colors at given interval
* ``/customdisco <interval>`` cycle through random colors at given interval
* ``/customday <interval> [#aabbcc #abc ...]`` cycle through specified colors with smooth transition
* ``/customday <interval>`` cycle through random colors with smooth transition

.. codeauthor:: Liza
"""

from random import choice
from twisted.internet.task import LoopingCall
from piqueserver.commands import command
from pyspades.color import interpolate_hsb, interpolate_rgb, hsb_to_rgb


def hex2rgb(h):
    h = h.strip('#')
    if len(h) == 3:
        h = ''.join([x*2 for x in h])
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

@command(admin_only=True)
def fog(connection, *args):
    """
    Set the fog color
    /fog red green blue (all values 0-255)
    /fog #aabbcc        (hex representation of rgb)
    /fog #abc           (short hex representation of rgb)
    /fog ?              (current fog color)
    """
    if (len(args) == 3):
        r = int(args[0])
        g = int(args[1])
        b = int(args[2])
    elif (len(args) == 1 and args[0][0] == '#'):
        if args[0] == '?':
            return connection.protocol.fog_color
        r, g, b = hex2rgb(args[0])
    else:
        raise ValueError("Neither RGB or hex code provided")

    old_fog_color = connection.protocol.fog_color
    connection.protocol.set_fog_color((r, g, b))
    if old_fog_color == (r, g, b):
        return ('Fog color changed successfully\n'
                'Warning: fog color set to same color as before')
    return 'Fog color changed successfully'

@command(admin_only=True)
def customdisco(connection, interval=None, *colors):
    """
    Cycle through different fog colors at given interval
    /customdisco <interval> [#aabbcc #abc ...] - colors are random unless specified
    """
    if interval:
        if colors:
            if len(colors) < 2:
                raise ValueError('Atleast two colors are required')
            colors = [hex2rgb(x) for x in colors]
            if float(interval) < 0.01:
                interval = 0.01
            connection.protocol.start_fog_cycle(float(interval), colors)
        else:
            connection.protocol.start_fog_cycle(float(interval), is_random=True)
    else:
        connection.protocol.stop_fog_cycle()

@command(admin_only=True)
def customday(connection, interval=None, *colors):
    """
    Cycle through different fog colors with smooth transition
    /customday <interval> [#aabbcc #abc ...] - colors are random unless specified
    """
    if interval:
        if colors:
            if len(colors) < 2:
                raise ValueError('Atleast two colors are required')
            colors = [hex2rgb(x) for x in colors]
            if float(interval) < 0.1:
                interval = 0.1
            connection.protocol.start_fog_cycle(int(float(interval) * 10), colors, is_smooth=True)
        else:
            connection.protocol.start_fog_cycle(int(float(interval) * 10), is_random=True, is_smooth=True)
    else:
        connection.protocol.stop_fog_cycle()


def apply_script(protocol, connection, config):
    class CustomFogProtocol(protocol):
        is_fog_active = False
        original_fog_color = protocol.fog_color
        fog_colors = []
        is_fog_random = False
        is_fog_smooth = False
        fog_interval = None
        fog_n = 0

        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.fog_loop = LoopingCall(self.update_fog_color)

        def update_fog_color(self):
            if self.is_fog_smooth:
                if self.is_fog_random:
                    if self.fog_n % self.fog_interval == 0:
                        self.fog_colors = [self.fog_colors[-1], (choice(range(255)), choice(range(255)), choice(range(255)))]
                    self.set_fog_color(interpolate_rgb(self.fog_colors[0], self.fog_colors[1], self.fog_n % self.fog_interval / self.fog_interval))
                else:
                    color_a = self.fog_n % (len(self.fog_colors) * self.fog_interval) // self.fog_interval
                    color_b = (self.fog_n + self.fog_interval) % (len(self.fog_colors) * self.fog_interval) // self.fog_interval
                    self.set_fog_color(interpolate_rgb(self.fog_colors[color_a], self.fog_colors[color_b], self.fog_n % self.fog_interval / self.fog_interval))
            else:
                if self.is_fog_random:
                    self.set_fog_color((choice(range(255)), choice(range(255)), choice(range(255))))
                else:
                    self.set_fog_color(self.fog_colors[self.fog_n % len(self.fog_colors)])

            self.fog_n += 1

        def start_fog_cycle(self, interval, colors=[], is_random=False, is_smooth=False):
            if self.is_fog_active:
                self.stop_fog_cycle()
            self.is_fog_active = True
            self.fog_colors = colors
            self.is_fog_random = is_random
            self.fog_n = 0
            if is_smooth:
                self.is_fog_smooth = is_smooth
                self.fog_interval = interval
                self.fog_colors = [
                    (choice(range(255)), choice(range(255)), choice(range(255))),
                    (choice(range(255)), choice(range(255)), choice(range(255)))
                    ]
                self.fog_loop.start(0.1)
            else:
                self.fog_loop.start(interval)

        def stop_fog_cycle(self):
            self.fog_loop.stop()
            self.is_fog_active = False
            self.is_fog_smooth = False
            self.set_fog_color(self.original_fog_color)

    return CustomFogProtocol, connection
