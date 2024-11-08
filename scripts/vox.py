"""
Builds and saves models in MagicaVoxel format
Put your *.vox files in ~/config/vox folder

Requires numpy

Credits to VoxBox project for code to handle MagicaVoxel format: https://github.com/DavidWilliams81/voxbox

Commands
^^^^^^^^

* ``/loadvox <filename>`` place .vox file

.. codeauthor:: Liza
"""

import numpy as np
import os, random, struct
from piqueserver.commands import command
from piqueserver.config import config
from pyspades.common import make_color
from pyspades.constants import BUILD_BLOCK
from pyspades.contained import BlockAction, SetColor
from twisted.internet.task import LoopingCall

voxdir = os.path.join(config.config_dir, 'vox')


def build(con, x, y, z, rgb, dither, rgbshift):
    dither = random.choice(range(-int(dither), int(dither)+1))
    rgb = [int(value) + dither + rgbshift for value in rgb]
    rgb = [255 if value > 255 else value for value in rgb]
    rgb = tuple([0 if value < 0 else value for value in rgb])
    set_color = SetColor()
    set_color.player_id = 32
    set_color.value = make_color(*rgb)
    con.protocol.broadcast_contained(set_color)
    block_action = BlockAction()
    block_action.player_id = 32
    block_action.value = BUILD_BLOCK
    block_action.x = x
    block_action.y = y
    block_action.z = z
    con.protocol.broadcast_contained(block_action)
    con.protocol.map.set_point(x, y, z, rgb)

@command(admin_only=True)
def loadvox(con, fn=None, dither=0, rotate='', shift=1, pattern='', px=None, py=None, pz=None):
    """
    Place .vox file
    /loadvox <filename> <dither 0-127 (default 0)> <rotate ([[x]-axis, [y]-axis, [z]-axis), flip ([h]orizontal, [v]ertical) - can be combined> <shift> <pattern>
    """
    if not pz:
        px, py, pz = con.get_location()
    paths = [x[:-4] for x in os.listdir(voxdir) if x.endswith('.vox')]
    rgbshift = 0
    if pattern:
        if pattern == 'brick':
            pattern = np.reshape([random.choice(range(-int(dither), int(dither)+1)) for x in range(256*256*64)], (256, 256, 64))
        dither = 0
    if fn in paths:
        path = os.path.join(voxdir, fn + '.vox')
        data, palette = read(path)
        layer = data[0]
        rotate += 'y'
        for char in rotate:
            if char == 'x':
                layer = np.rot90(layer, axes=(0,1))
            elif char == 'y':
                layer = np.rot90(layer, axes=(0,2))
            elif char == 'z':
                layer = np.rot90(layer, axes=(1,2))
            elif char == 'h':
                layer = np.fliplr(layer)
            elif char == 'v':
                layer = np.flipud(layer)
        if shift == 'center':
            px -= len(layer) // 2
            py -= len(layer[0]) // 2
            shift = 0
        for x in range(len(layer)):
            for y in range(len(layer[0])):
                for z in range(len(layer[0][0])):
                    if layer[x][y][z] != 0:
                        x1 = int(px)+x+int(shift)
                        y1 = int(py)+y+int(shift)
                        z1 = int(pz)-z+2
                        if (x1 in range(512)) and (y1 in range(512)) and (z1 in range(64)):
                            if pattern:
                                rgbshift = pattern[(x1+z1%2)//2][(y1+z1%2)//2][(z1+z1%2)//2-1]
                            con.vox_queue += [(x1, y1, z1, palette[layer[x][y][z]][:3], dither, rgbshift)]
        con.vox_build_start()
        return 'Model loaded'
    else:
        return 'Available models: ' + ', '.join(paths)

@command(admin_only=True)
def voxbrush(con, fn=None, dither=0, rotate='', pattern='', shift='center'):
    """
    Place .vox file by clicking
    /voxbrush <filename> <dither 0-127 (default 0)> <rotate ([[x]-axis, [y]-axis, [z]-axis), flip ([h]orizontal, [v]ertical) - can be combined> <pattern>
    """
    if con.voxbrush:
        if fn:
            con.voxbrush = (fn, dither, rotate, shift, pattern)
            return 'Vox brush updated'
        else:
            con.voxbrush = False
            return 'Vox brush disabled'
    else:
        con.voxbrush = (fn, dither, rotate, shift, pattern)
        return 'Vox brush enabled'

@command(admin_only=True)
def savevox(con, fn=None):
    """
    Save selection into a .vox file
    /savevox <filename>
    """
    if fn:
        if con.savevox_point_a:
            if con.savevox_point_b:
                c = list(zip(con.savevox_point_a, con.savevox_point_b))
                v = np.zeros((max(c[2])-min(c[2])+1, max(c[1])-min(c[1])+1, max(c[0])-min(c[0])+1), np.uint8)
                palette = [(0, 0, 0, 0)]
                for x in range(min(c[0]), max(c[0])+1):
                    for y in range(min(c[1]), max(c[1])+1):
                        for z in range(min(c[2]), max(c[2])+1):
                            color = con.protocol.world.map.get_color(x, y, z)
                            if color:
                                r, g, b = color
                                rgba = (r, g, b, 255)
                                if rgba not in palette:
                                    palette += [rgba]
                                i = palette.index(rgba)
                                if i > 255:
                                    return "Can't save more than 255 colors"
                            else:
                                i = 0
                            v[max(c[2])-z][y-min(c[1])][max(c[0])-x] = i
                palette = np.pad(palette, ((0, 256-len(palette)), (0, 0)))
                write([v], fn, np.array(palette, np.uint8))
                con.savevox_selection = False
                con.savevox_point_a = None
                con.savevox_point_b = None
                return 'File saved'
        return 'Create selection first'
    else:
        if con.savevox_selection:
            con.savevox_selection = False
            con.savevox_point_a = None
            con.savevox_point_b = None
            return 'Selection cancelled'
        else:
            con.savevox_selection = True
            con.savevox_point_a = None
            con.savevox_point_b = None
            return 'Selection started. Select two points by clicking on corner blocks'


def apply_script(protocol, connection, config):
    class VoxConnection(connection):

        def __init__(self, *arg, **kw):
            connection.__init__(self, *arg, **kw)
            self.savevox_selection = False
            self.savevox_point_a = None
            self.savevox_point_b = None
            self.vox_loop = None
            self.vox_queue = []
            self.voxbrush = False

        def on_shoot_set(self, state):
            if state == True:
                if self.voxbrush:
                    if not self.vox_queue:
                        coords = self.world_object.cast_ray(160)
                        if coords:
                            x, y, z = coords
                            loadvox(self, *self.voxbrush, x, y, z-3)
                if self.savevox_selection:
                    coords = self.world_object.cast_ray(160)
                    if self.savevox_point_a:
                        self.savevox_point_b = coords
                        self.send_chat('Selection created. Use /savevox <filename> to save selected area')
                    else:
                        self.savevox_point_a = coords
                        self.send_chat('First corner has been selected')
            connection.on_shoot_set(self, state)

        def vox_build_start(self):
            self.vox_queue = iter(self.vox_queue)
            self.vox_loop = LoopingCall(self.vox_queue_build)
            self.vox_loop.start(0.01)

        def vox_queue_build(self):
            for i in range(60):
                try:
                    block = next(self.vox_queue)
                    if block:
                        build(self, *block)
                except StopIteration:
                    self.vox_loop.stop()
                    self.vox_queue = []
                    break

    return protocol, VoxConnection


"""
Code for working with MagicaVoxel files
All credits to VoxBox project: https://github.com/DavidWilliams81/voxbox
"""

def write_chunk(id, chunk_content, child_chunks):
    
    data = bytearray(id)
    
    chunk_content_length = len(chunk_content) if chunk_content else 0
    child_chunks_length = len(child_chunks) if child_chunks else 0
    data = data + struct.pack('ii', chunk_content_length, child_chunks_length)
    
    if chunk_content:
        data = data + chunk_content
        
    if child_chunks:
        data = data + child_chunks
    return data

def write_size_chunk(volume):
    
    chunk_content = struct.pack('iii', len(volume[0][0]), len(volume[0]), len(volume))
    return write_chunk(b'SIZE', chunk_content, None)
    
def write_xyzi_chunk(volume):
    
    values = np.extract(volume, volume)
    (x, y, z) = np.nonzero(volume)
    voxels = np.stack([z.astype(np.uint8), y.astype(np.uint8), x.astype(np.uint8), values])
    voxels = voxels.transpose()
    voxels = voxels.reshape(-1)
    
    chunk_content = struct.pack('i', len(values))
    chunk_content += bytearray(voxels.tobytes())
                    
    return write_chunk(b'XYZI', chunk_content, None)
    
def write_pack_chunk(volume_list):
    
    chunk_content = struct.pack('i', len(volume_list))
    return write_chunk(b'PACK', chunk_content, None)
    
def write_rgba_chunk(palette):
    
    chunk_content = bytearray(palette[1:256].tobytes())
    chunk_content += struct.pack('xxxx')    
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
    data = data + struct.pack('i', 150);
    data = data + write_main_chunk(volume_list, palette)
    
    file = open(os.path.join(voxdir, filename + '.vox'), "wb")
    file.write(data)
    file.close()

def read_chunk(data):
    
    id, data = data[:4], data[4:]
    
##    print(id)
    
    (chunk_content_size, child_chunks_size), data = struct.unpack("II", data[:8]), data[8:]
    
    chunk_content = data[0 : chunk_content_size]
    child_chunks = data[chunk_content_size : chunk_content_size + child_chunks_size]
    
    while len(child_chunks) > 0:
    
        child_chunk_size = read_chunk(child_chunks)
        
        child_chunks = child_chunks[child_chunk_size:]
    
    return 4 + 8 + chunk_content_size + child_chunks_size
    
def read_size_chunk(file):

    (col_count, row_count, plane_count) = struct.unpack("III", file.read(12))
    
##    print("size", col_count, row_count, plane_count)
    
    return np.zeros((plane_count, row_count, col_count), dtype=np.uint8)
    
def read_xyzi_chunk(file, volume_to_fill):
    
    (voxel_count,) = struct.unpack("I", file.read(4))
    #chunk_content = chunk_content[4:]

    for i in range(voxel_count):
        
        (col, row, plane, index) = struct.unpack("BBBB", file.read(4))        
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
    
    (chunk_content_size, child_chunks_size) = struct.unpack("II", file.read(8))
    
##    print(chunk_content_size, child_chunks_size)
    
    palette = None
    volume_list = []
    
    while True:
        
        id=file.read(4)
        if not id: break
            
        (chunk_content_size, child_chunks_size) = struct.unpack("II", file.read(8))
        
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
    (ver,) = struct.unpack("I", file.read(4))
    

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
