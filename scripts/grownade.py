"""
Turns your grenades into magical kv6-growing seeds. Or beans!

Use ``/model <filename>`` to load model files. These must be placed inside a
folder named :file:`kv6/` in the config directory. A full path would look like
this: :file:`~/config/kv6/{filename}.kv6`. Then it can be loaded with ``/model
some_model``

Wildcards and subfolders are allowed. Some examples::

    /model building*

Loads all models that start with "building", like "building1" and
"buildingred"::

    /model my_trees/*

Loads all models inside a folder named "my_trees"

When you have many models loaded, each grenade will pick a random one to grow.
To stop littering the map with random objects just type ``/model``.

Pivot
^^^^^

THE PIVOT POINT in kv6 files determines the first block to be placed. The rest
of the model will then follow, growing around it.

The pivot point MUST be sitting on a block, or the model won't load. Checking
'Adjust pivots' in the Tools menu in SLAB6 will show handy coordinates.
To be sure, you can move the pivot to *half* of a block, e.g.: (4.50, 4.50, 8.50)

In a tree kv6, for example, the pivot point would lie on the lowest block of the
tree trunk, so that it grows up and not into the ground.

Works best with 0.75 kv6 models.

You can adjust FLYING_MODELS and GROW_ON_WATER to allow growing in the air and
on water, respectively. These are disabled by default so you can fly high and
sprinkle tree-growing grenades without worrying about unseemly oddities.

Options
^^^^^^^

.. code-block:: toml

    [grownade]

    flying_models = True # if False grenades exploding in midair will be ignored
    grow_on_water = True # if False grenades exploding in water will do nothing

.. codeauthor:: hompy
"""

import os
from glob import glob
from struct import pack, unpack
from random import choice
from itertools import product
from collections import deque, namedtuple
from twisted.internet.reactor import seconds
from twisted.internet.task import LoopingCall
from pyspades.contained import BlockAction, SetColor
from pyspades.common import make_color
from pyspades.constants import BUILD_BLOCK
from piqueserver.commands import command, player_only
from piqueserver.config import config

try:
    import numpy as np
except:
    print("grownade.py .vox support is disabled, because NumPy is not found. Do 'pip install numpy' to use .vox files with /model command")

grownade_section = config.section("grownade")
FLYING_MODELS = grownade_section.option("flying_models")
GROW_ON_WATER = grownade_section.option("grow_on_water")

KV6_DIR = os.path.join(config.config_dir, 'kv6')
VOX_DIR = os.path.join(config.config_dir, 'vox')
LOWEST_Z = 63 if GROW_ON_WATER.get() else 62
GROW_INTERVAL = 0.3

S_NO_KV6_FOLDER = "You haven't created a kv6 folder yet!"
S_NO_MATCHES = "Couldn't find any model files matching {expression}"
S_LOADED_SINGLE = 'Loaded model {filename}'
S_LOADED = 'Loaded {filenames}. Each grenade will pick one at random'
S_FAILED = 'Failed to load {filenames}'
S_PIVOT_TIP = 'Make sure the pivot points are correctly placed'
S_CANCEL = 'No longer spawning models'
S_SPECIFY_FILES = 'Specify model files to load. Wildcards are allowed, ' \
    'e.g.: "bunker", "tree*"'


class ModelLoadFailure(Exception):
    pass


def load_models(expression):# /model test2
    if not os.path.isdir(KV6_DIR):
        raise ModelLoadFailure(S_NO_KV6_FOLDER)
##    if not os.path.splitext(expression)[-1]:
##        # append default extension
##        expression += '.kv6'
    paths = glob(os.path.join(KV6_DIR, expression + '.kv6'))
    print(expression)
    print(paths)
    if not paths:
        paths = glob(os.path.join(VOX_DIR, expression + '.vox'))
        print(paths)
        if not paths:
            raise ModelLoadFailure(S_NO_MATCHES.format(expression=expression))

    # attempt to load models, discard invalid ones
    models, loaded, failed = [], [], []
    for path in paths:
        if path.endswith('.kv6'):
            model = KV6Model(path)
        elif path.endswith('.vox'):
            model = KV6Model(path)
        filename = os.path.split(path)[-1]
        if model.voxels:
            models.append(model)
            loaded.append(filename)
        else:
            failed.append(filename)
    return models, loaded, failed


@command('model', admin_only=True)
@player_only
def model_grenades(connection, expression=None):
    protocol = connection.protocol
    player = connection

    result = None
    if expression:
        try:
            models, loaded, failed = load_models(expression)
        except ModelLoadFailure as err:
            result = str(err)
        else:
            if len(loaded) == 1:
                result = S_LOADED_SINGLE.format(filename=loaded[0])
            elif len(loaded) > 1:
                result = S_LOADED.format(filenames=', '.join(loaded))

            if failed:
                player.send_chat(S_FAILED.format(filenames=', '.join(failed)))
                player.send_chat(S_PIVOT_TIP)

            if models:
                player.grenade_models = models

    elif player.grenade_models:
        player.grenade_models = None
        result = S_CANCEL
    else:
        result = S_SPECIFY_FILES
    if result:
        player.send_chat(result)


KV6Voxel = namedtuple('KV6Voxel', 'b g r a z neighbors normal_index')
NonSurfaceKV6Voxel = KV6Voxel(40, 64, 103, 128, 0, 0, 0)


class KV6Model:
    """
    Custom implementation that also generates non-surface voxels.
    Not suitable for general purpose.
    """

    size = None
    pivot = None
    voxels = None

    def __init__(self, path):
        with open(path, 'rb') as file:
            file.read(4)  # 'Kvxl'

            self.size = unpack('III', file.read(4 * 3))
            self.pivot = tuple(int(n) for n in unpack('fff', file.read(4 * 3)))

            voxel_count, = unpack('I', file.read(4))
            voxels = []
            for i in range(voxel_count):
                voxel = KV6Voxel._make(unpack('BBBBHBB', file.read(8)))
                voxels.append(voxel)

            size_x, size_y, size_z = self.size
            file.read(4 * size_x)  # discard extra information

            voxel_map = {}
            voxel_iter = iter(voxels)
            for x, y in product(range(size_x), range(size_y)):
                last_z = None
                column_len, = unpack('H', file.read(2))
                for i in range(column_len):
                    voxel = next(voxel_iter)
                    voxel_map[(x, y, voxel.z)] = voxel
                    if last_z is not None and not voxel.neighbors & 0b00010000:
                        for z in range(last_z + 1, voxel.z):
                            inside_voxel = NonSurfaceKV6Voxel._replace(z=z)
                            voxel_map[(x, y, z)] = inside_voxel
                    last_z = voxel.z

            if self.pivot not in voxel_map:
                return
            self.voxels = voxel_map
            print(self.size, self.pivot, self.voxels)


class VOXModel:
    pivot = None
    voxels = None

    def __init__(self, path):
##        with open(path, 'rb') as file:
##            data, palette = read(path)
##            layer = np.rot90(data[0], axes=(0,2))
##            self.pivot = tuple(len(layer) // 2, len(layer[0]) // 2, len(layer[0][0]) // 2)
##            palette[layer[x][y][z]][:3]
        self.voxels = {}
        self.voxels[(0, 0, 0)] = KV6Voxel(40, 64, 103, 128, 0, 0, 0)

##KV6Voxel = namedtuple('KV6Voxel', 'b g r a z neighbors normal_index')
##NonSurfaceKV6Voxel = KV6Voxel(40, 64, 103, 128, 0, 0, 0)

##            voxels = []
##            for i in range(voxel_count):
##                voxel = KV6Voxel._make(unpack('BBBBHBB', file.read(8)))
##                voxels.append(voxel)
##
##            size_x, size_y, size_z = self.size
##
##            voxel_map = {}
##            voxel_iter = iter(voxels)
##            for x, y in product(range(size_x), range(size_y)):
##                last_z = None
##                column_len, = unpack('H', file.read(2))
##                for i in range(column_len):
##                    voxel = next(voxel_iter)
##                    voxel_map[(x, y, voxel.z)] = voxel
##                    if last_z is not None and not voxel.neighbors & 0b00010000:
##                        for z in range(last_z + 1, voxel.z):
##                            inside_voxel = NonSurfaceKV6Voxel._replace(z=z)
##                            voxel_map[(x, y, z)] = inside_voxel
##                    last_z = voxel.z
##
##            if self.pivot not in voxel_map:
##                return
##            self.voxels = voxel_map


class BuildQueue:
    interval = 0.02
    blocks_per_cycle = 3
    blocks = None
    loop = None
    call_on_exhaustion = None

    def __init__(self, protocol, call_on_exhaustion=None):
        self.protocol = protocol
        self.blocks = deque()
        self.loop = LoopingCall(self.cycle)
        self.loop.start(self.interval)
        self.call_on_exhaustion = call_on_exhaustion

    def cycle(self):
        if not self.blocks:
            self.loop.stop()
            if self.call_on_exhaustion:
                self.call_on_exhaustion()
            return
        blocks_left = self.blocks_per_cycle
        last_color = None
        while self.blocks and blocks_left:
            x, y, z, color = self.blocks.popleft()
            if color != last_color:
                set_color = SetColor()
                set_color.value = make_color(*color)
                set_color.player_id = 32
                self.protocol.broadcast_contained(set_color, save=True)
                last_color = color
            if not self.protocol.map.get_solid(x, y, z):
                block_action = BlockAction()
                block_action.value = BUILD_BLOCK
                block_action.player_id = 32
                block_action.x = x
                block_action.y = y
                block_action.z = z
                self.protocol.broadcast_contained(block_action, save=True)
                self.protocol.map.set_point(x, y, z, color)
                blocks_left -= 1
        self.protocol.update_entities()

    def push_block(self, x, y, z, color):
        if not self.loop.running:
            self.loop.start(self.interval)
        self.blocks.append((x, y, z, color))


class GrowModel:
    model = None
    x, y, z = None, None, None
    open, closed = None, None
    build_queue = None
    grow_loop = None

    def __init__(self, protocol, model, x, y, z):
        self.protocol = protocol
        self.model = model
        self.x, self.y, self.z = x, y, z
        self.open = [model.pivot]
        self.closed = set()
        self.build_queue = BuildQueue(protocol, self.queue_exhausted)
        self.grow_loop = LoopingCall(self.grow_cycle)
        self.grow_loop.start(GROW_INTERVAL)

    def grow_cycle(self):
        new_nodes = set()
        for xyz in self.open:
            if xyz not in self.model.voxels or xyz in self.closed:
                continue
            self.closed.add(xyz)
            x, y, z = xyz
            new_nodes.add((x, y, z - 1))
            new_nodes.add((x, y, z + 1))
            new_nodes.add((x, y - 1, z))
            new_nodes.add((x, y + 1, z))
            new_nodes.add((x - 1, y, z))
            new_nodes.add((x + 1, y, z))
            p_x, p_y, p_z = self.model.pivot
            x, y, z = x + self.x - p_x, y + self.y - p_y, z + self.z - p_z
            if x < 0 or y < 0 or z < 0 or x >= 512 or y >= 512 or z >= LOWEST_Z:
                continue
            voxel = self.model.voxels[xyz]
            self.build_queue.push_block(x, y, z, (voxel.r, voxel.g, voxel.b))
        self.open = new_nodes
        if not new_nodes:
            self.grow_loop.stop()

    def queue_exhausted(self):
        if not self.open:
            self.release()

    def release(self):
        if self.build_queue.loop.running:
            self.build_queue.loop.stop()
        self.build_queue.loop = None
        if self.grow_loop.running:
            self.grow_loop.stop()
        self.grow_loop = None
        self.protocol.growers.remove(self)


def apply_script(protocol, connection, config):
    class SeedyConnection(connection):
        grenade_models = None

        def on_reset(self):
            self.grenade_models = None
            connection.on_reset(self)

        def on_grenade_thrown(self, grenade):
            if self.grenade_models:
                grenade.name = 'seed'
                grenade.callback = self.seed_exploded
            connection.on_grenade_thrown(self, grenade)

        def seed_exploded(self, grenade):
            if not self.grenade_models:
                return
            x, y, z = (int(n) for n in grenade.position.get())
            map = self.protocol.map
            if (not FLYING_MODELS.get() and not map.get_solid(x, y, z + 1) and
                    not z == LOWEST_Z == 63):
                return
            model = choice(self.grenade_models)
            grower = GrowModel(self.protocol, model, x, y, z)
            self.protocol.growers.append(grower)

    class SeedyProtocol(protocol):
        growers = None

        def on_map_change(self, map):
            self.growers = []
            protocol.on_map_change(self, map)

        def on_map_leave(self):
            for grower in self.growers[:]:
                grower.release()
            self.growers = None
            protocol.on_map_leave(self)

    return SeedyProtocol, SeedyConnection


"""
Code for working with MagicaVoxel files
All credits to VoxBox project: https://github.com/DavidWilliams81/voxbox
"""

def write_chunk(id, chunk_content, child_chunks):
    
    data = bytearray(id)
    
    chunk_content_length = len(chunk_content) if chunk_content else 0
    child_chunks_length = len(child_chunks) if child_chunks else 0
    data = data + pack('ii', chunk_content_length, child_chunks_length)
    
    if chunk_content:
        data = data + chunk_content
        
    if child_chunks:
        data = data + child_chunks
    return data

def write_size_chunk(volume):
    
    chunk_content = pack('iii', len(volume[0][0]), len(volume[0]), len(volume))
    return write_chunk(b'SIZE', chunk_content, None)
    
def write_xyzi_chunk(volume):
    
    values = np.extract(volume, volume)
    (x, y, z) = np.nonzero(volume)
    voxels = np.stack([z.astype(np.uint8), y.astype(np.uint8), x.astype(np.uint8), values])
    voxels = voxels.transpose()
    voxels = voxels.reshape(-1)
    
    chunk_content = pack('i', len(values))
    chunk_content += bytearray(voxels.tobytes())
                    
    return write_chunk(b'XYZI', chunk_content, None)
    
def write_pack_chunk(volume_list):
    
    chunk_content = pack('i', len(volume_list))
    return write_chunk(b'PACK', chunk_content, None)
    
def write_rgba_chunk(palette):
    
    chunk_content = bytearray(palette[1:256].tobytes())
    chunk_content += pack('xxxx')    
    return write_chunk(b'RGBA', chunk_content, None) 

def write_main_chunk(volume_list, palette):
    
    child_chunks  = write_pack_chunk(volume_list)
    for volume in volume_list:
        child_chunks += write_size_chunk(volume)
        child_chunks += write_xyzi_chunk(volume)
    
    if palette is not None:
        child_chunks += write_rgba_chunk(palette)
    
    return write_chunk(b'MAIN', None, child_chunks)
    
# This function expects a *list* of 3D NumPy arrays. If you only
# have one ( a single frame) then create a single element list.
def write(volume_list, filename, palette = None):
    
    if not isinstance(volume_list, list):
        raise TypeError("Argument 'volume_list' should be a list")
        
    if not all(type(volume) is np.ndarray for volume in volume_list):
        raise TypeError("All elements of 'volume_list' must be NumPy arrays")
        
    if not all(volume.ndim == 3 for volume in volume_list):
        raise TypeError("All volumes in 'volume_list' must be 3D")
    
    data = bytearray(b'VOX ')
    data = data + pack('i', 150);
    data = data + write_main_chunk(volume_list, palette)
    
    file = open(os.path.join(voxdir, filename + '.vox'), "wb")
    file.write(data)
    file.close()

def read_chunk(data):
    
    id, data = data[:4], data[4:]
    
##    print(id)
    
    (chunk_content_size, child_chunks_size), data = unpack("II", data[:8]), data[8:]
    
    chunk_content = data[0 : chunk_content_size]
    child_chunks = data[chunk_content_size : chunk_content_size + child_chunks_size]
    
    while len(child_chunks) > 0:
    
        child_chunk_size = read_chunk(child_chunks)
        
        child_chunks = child_chunks[child_chunk_size:]
    
    return 4 + 8 + chunk_content_size + child_chunks_size
    
def read_size_chunk(file):

    (col_count, row_count, plane_count) = unpack("III", file.read(12))
    
##    print("size", col_count, row_count, plane_count)
    
    return np.zeros((plane_count, row_count, col_count), dtype=np.uint8)
    
def read_xyzi_chunk(file, volume_to_fill):
    
    (voxel_count,) = unpack("I", file.read(4))
    #chunk_content = chunk_content[4:]

    for i in range(voxel_count):
        
        (col, row, plane, index) = unpack("BBBB", file.read(4))        
        volume_to_fill[plane][row][col] = index
                      
def read_rgba_chunk(file):
    
    # MagicaVoxel palette storage seems a little odd. The application allows
    # editing of 255 entries numbered 1-255, but these get saved to disk as
    # entries 0-254 in a 256-element array. The last element (255) appears to
    # be dummy data and might always be zero?
    byte_count = 4 * 256 # 256 entries with 4 bytes each
    palette = np.fromfile(file, dtype=np.uint8, count = byte_count)
    palette = palette.reshape((256, 4))
    palette = np.roll(palette, 1, axis=0)
    return palette
    
def read_pack_chunk(chunk_content):
    
    print("pack")
    
def read_main_chunk(file):
    
    (chunk_content_size, child_chunks_size) = unpack("II", file.read(8))
    
##    print(chunk_content_size, child_chunks_size)
    
    palette = None
    volume_list = []
    
    while True:
        
        id=file.read(4)
        if not id: break
            
        (chunk_content_size, child_chunks_size) = unpack("II", file.read(8))
        
        #print(id)
        
        #chunk_content = file.read(chunk_content_size)
        
        if id == b'SIZE':
            volume_list.append(read_size_chunk(file))            
        elif id == b'XYZI':
            read_xyzi_chunk(file, volume_list[-1])
        elif id == b'RGBA':
            palette = read_rgba_chunk(file)
        else:
            file.read(chunk_content_size) # Just consume it
            
    return volume_list, palette
            
        
    
def read(filename):
    
    file = open(filename, "rb")
    
    id = file.read(4)
    (ver,) = unpack("I", file.read(4))
    

    main_chunk_header = file.read(4)
    
    volume_list = read_main_chunk(file)

    file.close()

    return volume_list

# From MagicaVoxel file format description
default_palette_data = np.array(
    [0x00000000, 0xffffffff, 0xffccffff, 0xff99ffff, 0xff66ffff, 0xff33ffff, 0xff00ffff, 0xffffccff, 0xffccccff, 0xff99ccff, 0xff66ccff, 0xff33ccff, 0xff00ccff, 0xffff99ff, 0xffcc99ff, 0xff9999ff,
    0xff6699ff, 0xff3399ff, 0xff0099ff, 0xffff66ff, 0xffcc66ff, 0xff9966ff, 0xff6666ff, 0xff3366ff, 0xff0066ff, 0xffff33ff, 0xffcc33ff, 0xff9933ff, 0xff6633ff, 0xff3333ff, 0xff0033ff, 0xffff00ff,
    0xffcc00ff, 0xff9900ff, 0xff6600ff, 0xff3300ff, 0xff0000ff, 0xffffffcc, 0xffccffcc, 0xff99ffcc, 0xff66ffcc, 0xff33ffcc, 0xff00ffcc, 0xffffcccc, 0xffcccccc, 0xff99cccc, 0xff66cccc, 0xff33cccc,
    0xff00cccc, 0xffff99cc, 0xffcc99cc, 0xff9999cc, 0xff6699cc, 0xff3399cc, 0xff0099cc, 0xffff66cc, 0xffcc66cc, 0xff9966cc, 0xff6666cc, 0xff3366cc, 0xff0066cc, 0xffff33cc, 0xffcc33cc, 0xff9933cc,
    0xff6633cc, 0xff3333cc, 0xff0033cc, 0xffff00cc, 0xffcc00cc, 0xff9900cc, 0xff6600cc, 0xff3300cc, 0xff0000cc, 0xffffff99, 0xffccff99, 0xff99ff99, 0xff66ff99, 0xff33ff99, 0xff00ff99, 0xffffcc99,
    0xffcccc99, 0xff99cc99, 0xff66cc99, 0xff33cc99, 0xff00cc99, 0xffff9999, 0xffcc9999, 0xff999999, 0xff669999, 0xff339999, 0xff009999, 0xffff6699, 0xffcc6699, 0xff996699, 0xff666699, 0xff336699,
    0xff006699, 0xffff3399, 0xffcc3399, 0xff993399, 0xff663399, 0xff333399, 0xff003399, 0xffff0099, 0xffcc0099, 0xff990099, 0xff660099, 0xff330099, 0xff000099, 0xffffff66, 0xffccff66, 0xff99ff66,
    0xff66ff66, 0xff33ff66, 0xff00ff66, 0xffffcc66, 0xffcccc66, 0xff99cc66, 0xff66cc66, 0xff33cc66, 0xff00cc66, 0xffff9966, 0xffcc9966, 0xff999966, 0xff669966, 0xff339966, 0xff009966, 0xffff6666,
    0xffcc6666, 0xff996666, 0xff666666, 0xff336666, 0xff006666, 0xffff3366, 0xffcc3366, 0xff993366, 0xff663366, 0xff333366, 0xff003366, 0xffff0066, 0xffcc0066, 0xff990066, 0xff660066, 0xff330066,
    0xff000066, 0xffffff33, 0xffccff33, 0xff99ff33, 0xff66ff33, 0xff33ff33, 0xff00ff33, 0xffffcc33, 0xffcccc33, 0xff99cc33, 0xff66cc33, 0xff33cc33, 0xff00cc33, 0xffff9933, 0xffcc9933, 0xff999933,
    0xff669933, 0xff339933, 0xff009933, 0xffff6633, 0xffcc6633, 0xff996633, 0xff666633, 0xff336633, 0xff006633, 0xffff3333, 0xffcc3333, 0xff993333, 0xff663333, 0xff333333, 0xff003333, 0xffff0033,
    0xffcc0033, 0xff990033, 0xff660033, 0xff330033, 0xff000033, 0xffffff00, 0xffccff00, 0xff99ff00, 0xff66ff00, 0xff33ff00, 0xff00ff00, 0xffffcc00, 0xffcccc00, 0xff99cc00, 0xff66cc00, 0xff33cc00,
    0xff00cc00, 0xffff9900, 0xffcc9900, 0xff999900, 0xff669900, 0xff339900, 0xff009900, 0xffff6600, 0xffcc6600, 0xff996600, 0xff666600, 0xff336600, 0xff006600, 0xffff3300, 0xffcc3300, 0xff993300,
    0xff663300, 0xff333300, 0xff003300, 0xffff0000, 0xffcc0000, 0xff990000, 0xff660000, 0xff330000, 0xff0000ee, 0xff0000dd, 0xff0000bb, 0xff0000aa, 0xff000088, 0xff000077, 0xff000055, 0xff000044,
    0xff000022, 0xff000011, 0xff00ee00, 0xff00dd00, 0xff00bb00, 0xff00aa00, 0xff008800, 0xff007700, 0xff005500, 0xff004400, 0xff002200, 0xff001100, 0xffee0000, 0xffdd0000, 0xffbb0000, 0xffaa0000,
    0xff880000, 0xff770000, 0xff550000, 0xff440000, 0xff220000, 0xff110000, 0xffeeeeee, 0xffdddddd, 0xffbbbbbb, 0xffaaaaaa, 0xff888888, 0xff777777, 0xff555555, 0xff444444, 0xff222222, 0xff111111],
    dtype=np.uint32)
    
default_palette_view = default_palette_data.view(np.uint8)

default_palette = default_palette_view.reshape(256,4)
