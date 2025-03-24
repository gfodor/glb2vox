import struct
import sys

def read_int(f):
    """Read a 4-byte little-endian integer from file."""
    return struct.unpack('<i', f.read(4))[0]

def convert_poly2vox_to_magicavoxel(poly2vox_file, magicavoxel_file):
    """
    Convert a poly2vox .vox file to MagicaVoxel .vox format (version 150).
    
    Args:
        poly2vox_file (str): Path to input poly2vox .vox file
        magicavoxel_file (str): Path to output MagicaVoxel .vox file
    """
    # Read poly2vox file
    with open(poly2vox_file, 'rb') as f:
        xsiz = read_int(f)
        ysiz = read_int(f)
        zsiz = read_int(f)
        voxel_data = f.read(xsiz * ysiz * zsiz)
        palette = f.read(256 * 3)  # Assuming 256 RGB colors (768 bytes)

    # Process voxel data: collect set voxels (value != 255)
    voxels = []
    for z in range(zsiz):
        for y in range(ysiz):
            for x in range(xsiz):
                #idx = x + y * xsiz + z * xsiz * ysiz
                idx = z + y * zsiz + x * zsiz * ysiz
                v = voxel_data[idx]
                if v != 255:
                    if v == 0:
                        color_index = 255  # Default color for internal voxels
                    else:
                        color_index = v  # Surface voxels use v directly (1-254)
                    voxels.append((x, y + 1, z + 1, color_index))

    # Prepare MagicaVoxel palette: 256 RGBA colors
    mv_palette = []  # Index 0: unused, set to transparent black
    for i in range(1, 255):
        r = palette[i * 3]
        g = palette[i * 3 + 1]
        b = palette[i * 3 + 2]
        mv_palette.append((r, g, b, 255))  # Indices 1-255: poly2vox[0-254] with A=255

    mv_palette.append((0, 0, 0, 0))  # Indices 1-255: poly2vox[0-254] with A=255

    # Build MagicaVoxel chunks
    # SIZE chunk: dimensions
    size_content = struct.pack('<iii', xsiz, ysiz, zsiz)
    size_chunk = b'SIZE' + struct.pack('<ii', len(size_content), 0) + size_content

    # XYZI chunk: voxel list
    num_voxels = len(voxels)
    xyzi_content = struct.pack('<i', num_voxels)
    for x, y, z, c in voxels:
        xyzi_content += struct.pack('<BBBB', x, ysiz - y, zsiz - z, c)
    xyzi_chunk = b'XYZI' + struct.pack('<ii', len(xyzi_content), 0) + xyzi_content

    # RGBA chunk: palette
    rgba_content = b''
    for r, g, b, a in mv_palette:
        rgba_content += struct.pack('<BBBB', r * 4, g * 4, b * 4, a)
    rgba_chunk = b'RGBA' + struct.pack('<ii', len(rgba_content), 0) + rgba_content

    # MAIN chunk: contains SIZE, XYZI, RGBA
    children = size_chunk + xyzi_chunk + rgba_chunk
    main_chunk = b'MAIN' + struct.pack('<ii', 0, len(children)) + children

    # Assemble full file
    vox_file = b'VOX ' + struct.pack('<i', 150) + main_chunk

    # Write to output file
    with open(magicavoxel_file, 'wb') as f:
        f.write(vox_file)

# Example usage
if __name__ == "__main__":
    # Read input and output from args
    input_vox = sys.argv[1]
    output_vox = sys.argv[2]

    convert_poly2vox_to_magicavoxel(input_vox, output_vox)
