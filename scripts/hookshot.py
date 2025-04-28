import os
from math import sqrt
from piqueserver.config import config
from piqueserver.commands import command
from twisted.internet import reactor # as you can see i seriously wasnt trying at all this time


NOHOOK = []

try:
    with open(os.path.join(config.config_dir, 'no_hook.txt')) as f:
        NOHOOK = f.read().splitlines()
except:
    f = open(os.path.join(config.config_dir, 'no_hook.txt'), 'w')
    f.close()

@command('hook', 'hs')
def hook(self):
    """
    Use hookshot
    /hook, /hs
    """
    if self.world_object.cast_ray(self.hookshot_length) != None and self.disable_hook != True and self.has_intel != True:
        try:
            a,b,c = self.world_object.cast_ray(self.hookshot_length)
            d,e,f = self.world_object.position.get()
            g,h,i = self.world_object.orientation.get()
            self.disable_hook = True
            reactor.callLater(self.cooldown_time, unhook, self)
            set_loc(self, (a,b,c), (d,e,f), (g,h,i), 10) # man i should realy stop using so many tuples
        except:
            return False

@command('ho')
def toggle_hookshot(self):
    self.hooking = not self.hooking
    if self.hooking: 
        return 'The hookshot has been enabled!'
    else: 
        return 'The hookshot has been disabled!'

@command('hl')
def set_hookshot_length(self, value):
    self.hookshot_length = float(value)
    return 'Hookshot length set to %f.' % self.hookshot_length

@command('hc')
def set_hookshot_cooldown(self, value):
    self.cooldown_time = float(value)
    return 'Hookshot cooldown-time set to %f.' % self.cooldown_time

def unhook(hooker): # yeah that is basicaly what you are
    hooker.disable_hook = False

def set_loc(hooker, goal, posi, ori, counter):
    if counter > 255 or (posi[0] < 1 and not hooker.admin) or (posi[0] > 511 and not hooker.admin) or posi[1] < 1 or posi[1] > 512 or posi[2] >= 62 or (sqrt((goal[0]-posi[0])**2 + (goal[1]-posi[1])**2 + (goal[2]-posi[2])**2) <= 2) or hooker.protocol.map.get_solid(posi[0]+ori[0],posi[1]+ori[1],posi[2]+ori[2]) or hooker.protocol.map.get_solid(posi[0],posi[1],posi[2]-1): # dat line 
        return False
    elif not hooker.is_here:
        return False
    else: 
        reactor.callLater(0.01*counter, hooker.set_location, (posi[0],posi[1],posi[2]-1)) # who needs vertex3 when you can make everything more complicated
        return set_loc(hooker, goal, (posi[0]+ori[0], posi[1]+ori[1], posi[2]+ori[2]), ori, counter+1) # recursion to make it even more unreadable

@command()
def nohook(connection):
    """
    Toggle enabling hookshot on join
    /nohook
    """
    if connection.name in NOHOOK:
        NOHOOK.remove(connection.name)
        connection.send_chat('Hookshot will be enabled')
    else:
        NOHOOK.append(connection.name)
        connection.send_chat('Hookshot will be disabled')
    with open(os.path.join(config.config_dir, 'no_hook.txt'), 'w') as f:
        f.write('\n'.join(NOHOOK))


def apply_script(protocol, connection, config):

    class hooconnection(connection):
        painting = False
        hooking = True
        hookshot_length = 100 # 90
        cooldown_time = 0 # only for pussies
        disable_hook = False
        has_intel = False
        is_here = True

        #def on_hit(self, hit_amount, hit_player, type, grenade):
        #    hit_player.disable_hook = True
        #    reactor.callLater(self.cooldown_time, unhook, hit_player)
        #    return connection.on_hit(self, hit_amount, hit_player, type, grenade)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            if self.hooking and sneak and self.world_object.cast_ray(self.hookshot_length) != None and self.disable_hook != True and self.has_intel != True and self.painting != True and self.jetpack != True:
                try:
                    a,b,c = self.world_object.cast_ray(self.hookshot_length)
                    d,e,f = self.world_object.position.get()
                    g,h,i = self.world_object.orientation.get()
                    self.disable_hook = True
                    reactor.callLater(self.cooldown_time, unhook, self)
                    set_loc(self, (a,b,c), (d,e,f), (g,h,i), 10) # man i should realy stop using so many tuples
                except:
                    return False
            return connection.on_animation_update(self, jump, crouch, sneak, sprint)

        def on_login(self, name):
            connection.on_login(self, name)
            if self.name in NOHOOK:
                self.hooking = False

        def on_flag_take(u):
            u.has_intel = True
            return connection.on_flag_take(u)

        def on_flag_drop(still_u):
            still_u.has_intel = False
            return connection.on_flag_drop(still_u)

        def on_flag_capture(its_u_again):
            its_u_again.has_intel = False
            return connection.on_flag_capture(its_u_again)

        def on_disconnect(self):
            self.is_here = False
            return connection.on_disconnect(self)

    return protocol, hooconnection
