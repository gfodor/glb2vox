"""
    This script is designed to export a mass amount of MagicaVoxel .vox files
    to .obj. Unlike Magica's internal exporter, this exporter preserves the
    voxel vertices for easy manipulating in a 3d modeling program like Blender.

    Various meshing algorithms are included (or to be included). MagicaVoxel
    uses monotone triangulation (I think). The algorithms that will (or do)
    appear in this script will use methods to potentially reduce rendering
    artifacts that could be introduced by triangulation of this nature.

    I may also include some features like light map generation for easy
    importing into Unreal Engine, etc.

    Notes:
        * There may be a few floating point equality comparisons. They seem to
            work but it scares me a little.
        * TODO: use constants instead of magic numbers (as defined in AAQuad),
                (i.e., ..., 2 -> AAQuad.TOP, ...)
        * A lot of assertions should probably be exceptions since they are
            error checking user input (this sounds really bad now that I've put
            it on paper...). So don't run in optimized mode (who does that
            anyways?).
        * I am considering adding FBX support.

    Written by Shivshank and Claytone
"""
import math
import logging
import os
import shutil
import time
log = logging.getLogger()


class AAQuad:
    """ A solid colored axis aligned quad. """
    normals = [
        (-1, 0, 0),  # left = 0
        (1, 0, 0),  # right = 1
        (0, 0, 1),  # top = 2
        (0, 0, -1),  # bottom = 3
        (0, -1, 0),  # front = 4
        (0, 1, 0)  # back = 5
    ]
    LEFT = 0
    RIGHT = 1
    TOP = 2
    BOTTOM = 3
    FRONT = 4
    BACK = 5

    def __init__(self, verts, uv=None, normal=None):
        assert len(verts) == 4, "face must be a quad"
        self.vertices = verts
        self.uv = uv
        self.normal = normal

    def __str__(self):
        s = []
        for i in self.vertices:
            s.append(str(i) + '/' + str(self.uv) + '/' + str(self.normal))
        return 'f ' + ' '.join(s)

    def center(self):
        return (
            sum(i[0] for i in self.vertices) / 4,
            sum(i[1] for i in self.vertices) / 4,
            sum(i[2] for i in self.vertices) / 4
        )


def bucket_hash(faces, origin, maximum, bucket=16):
    extents = (
        math.ceil((maximum[0] - origin[0]) / bucket),
        math.ceil((maximum[1] - origin[1]) / bucket),
        math.ceil((maximum[2] - origin[2]) / bucket)
    )
    buckets = {}
    for f in faces:
        c = f.center()
        # TODO


def optimized_greedy_mesh(faces):
    # TODO
    edges = adjacency_graph_edges(faces)
    groups = contiguous_faces(faces, edges)
    return faces


def adjacency_graph_edges(faces):
    """ Get the list of edges representing adjacent faces. """
    # a list of edges, where edges are tuple(face_a, face_b)
    edges = []
    # build the list of edges in the graph
    for root in faces:
        for face in faces:
            if face is root:
                continue
            if faces_are_adjacent(root, face):
                # the other edge will happen somewhere else in the iteration
                # (i.e., the relation isAdjacent is symmetric)
                edges.append((root, face))
    return edges


def contiguous_faces(faces, adjacency_graph_edge_list):
    """ Get the list of connected components from a list of graph edges.
        The list will contain lists containing the edges within the components.
    """
    groups = []
    visited = dict((f, False) for f in faces)
    for face in faces:
        # if the face hasn't been visited, it is not in any found components
        if not visited[face]:
            g = []
            _visit_graph_nodes(face, adjacency_graph_edge_list, visited, g)
            # there is only a new component if face has not been visited yet
            groups.append(g)
    return groups


def _visit_graph_nodes(node, edges, visited, component):
    """ Recursive routine used in findGraphComponents """
    # visit every component connected to this one
    for edge in edges:
        # for all x in nodes, (node, x) and (x, node) should be in edges!
        # therefore we don't have to check for "edge[1] is node"
        if edge[0] is node and not visited[edge[1]]:
            assert edge[1] is not node, "(node, node) should not be in edges"
            # mark the other node as visited
            visited[edge[1]] = True
            component.append(edge[1])
            # visit all of that nodes connected nodes
            _visit_graph_nodes(edge[1], edges, visited, component)


def faces_are_adjacent(a, b):
    """ Adjacent is defined as same normal, uv, and a shared edge.
        This isn't entirely intuitive (i.e., corner faces are not adjacent)
        but this definition fits the problem domain.
        Only works on AAQuads.
    """
    # note: None is == None, this shouldn't matter
    if a.uv != b.uv:
        return False
    if a.normal != b.normal:
        return False
    # to be adjacent, two faces must share an edge
    # use == and not identity in case edge split was used
    shared = 0
    for vert_a in a.vertices:
        for vert_b in b.vertices:
            if vert_a == vert_b:
                shared += 1
            # hooray we have found a shared edge (or a degenerate case...)
            if shared == 2:
                return True
    return False


class GeoFace:
    """ An arbitrary geometry face
        This should only be used for arbitrary models, not ones we can
        reasonably assume are axis aligned.
    """

    def __init__(self, verts, uvs=None, normals=None):
        self.vertices = verts
        assert len(verts) in (3, 4), "only quads and tris are supported"
        self.normals = normals
        self.uvs = uvs

    def to_aa_quad(self, skip_assert=False):
        q = AAQuad(self.vertices)
        if self.normals is not None and len(self.normals) > 0:
            if not skip_assert:
                for i in self.normals:
                    assert self.normals[0] == i, \
                        "face must be axis aligned (orthogonal normals)"
            q.normal = self.normals[0]
        if self.uvs is not None and len(self.uvs) > 0:
            if not skip_assert:
                for i in self.uvs:
                    assert self.uvs[0] == i, \
                        "face must be axis aligned (orthogonal)"
            q.uv = self.uvs[0]
        return q


# MagicaVoxel does -.5 to +.5 for each cube, we'll do 0.0 to 1.0
def _get_front_side(voxel):
    return (
        (voxel.x, voxel.y, voxel.z + 1),
        (voxel.x, voxel.y, voxel.z),
        (voxel.x + 1, voxel.y, voxel.z),
        (voxel.x + 1, voxel.y, voxel.z + 1)
    )


def _get_back_side(voxel):
    return (
        (voxel.x + 1, voxel.y + 1, voxel.z + 1),
        (voxel.x + 1, voxel.y + 1, voxel.z),
        (voxel.x, voxel.y + 1, voxel.z),
        (voxel.x, voxel.y + 1, voxel.z + 1)
    )


def _get_left_side(voxel):
    return [
        (voxel.x, voxel.y + 1, voxel.z + 1),
        (voxel.x, voxel.y + 1, voxel.z),
        (voxel.x, voxel.y, voxel.z),
        (voxel.x, voxel.y, voxel.z + 1)
    ]


def _get_right_side(voxel):
    return (
        (voxel.x + 1, voxel.y, voxel.z + 1),
        (voxel.x + 1, voxel.y, voxel.z),
        (voxel.x + 1, voxel.y + 1, voxel.z),
        (voxel.x + 1, voxel.y + 1, voxel.z + 1)
    )


def _get_top_side(voxel):
    return (
        (voxel.x, voxel.y + 1, voxel.z + 1),
        (voxel.x, voxel.y, voxel.z + 1),
        (voxel.x + 1, voxel.y, voxel.z + 1),
        (voxel.x + 1, voxel.y + 1, voxel.z + 1)
    )


def _get_bottom_side(voxel):
    return (
        (voxel.x, voxel.y, voxel.z),
        (voxel.x, voxel.y + 1, voxel.z),
        (voxel.x + 1, voxel.y + 1, voxel.z),
        (voxel.x + 1, voxel.y, voxel.z)
    )


def _get_obj_faces_support(side, color, faces, out_faces):
    n = AAQuad.normals[side]
    # note: texcoords are based on MagicaVoxel's texturing scheme!
    #   meaning a color index of 0 translates to pixel[255]
    #   and color index [1:256] -> pixel[0:255]
    u = ((color - 1) / 256 + 1 / 512, 0.5)
    out_faces.append(
        AAQuad(faces, u, n)
    )


class VoxelStruct:
    """ Describes a voxel object
    """

    def __init__(self):
        # a dict is probably the best way to go about this
        # (as a trade off between performance and code complexity)
        # see _index for the indexing method
        self.voxels = {}
        self.colorIndices = set()

    def from_list(self, voxels):
        self.voxels = {}
        for voxel in voxels:
            self.set_voxel(voxel)
            self.colorIndices.add(voxel.colorIndex)

    def set_voxel(self, voxel):
        self.voxels[voxel.z * (256 ** 2) + voxel.y * 256 + voxel.x] = voxel

    def get_voxel(self, x, y, z):
        return self.voxels.get(z * (256 ** 2) + y * 256 + x, None)

    @staticmethod
    def _index(x, y, z):
        return z * (256 ** 2) + y * 256 + x

    def get_bounds(self):
        origin = (float("inf"), float("inf"), float("inf"))
        maximum = (float("-inf"), float("-inf"), float("-inf"))
        for key, voxel in self.voxels.items():
            origin = (
                min(origin[0], voxel.x),
                min(origin[1], voxel.y),
                min(origin[2], voxel.z)
            )
            maximum = (
                max(maximum[0], voxel.x),
                max(maximum[1], voxel.y),
                max(maximum[2], voxel.z)
            )
        return origin, maximum

    def zero_origin(self):
        """ Translate the model so that it's origin is at 0, 0, 0 """
        origin, maximum = self.get_bounds()
        result = {}
        x_off, y_off, z_off = origin
        for key, voxel in self.voxels.iteritems():
            result[self._index(voxel.x - x_off, voxel.y - y_off, voxel.z - z_off)] = \
                Voxel(voxel.x - x_off, voxel.y - y_off, voxel.z - z_off,
                      voxel.colorIndex)
        self.voxels = result
        return (0, 0, 0), (maximum[0] - x_off,
                           maximum[1] - y_off,
                           maximum[2] - z_off)

    def to_quads(self):
        """ --> a list of AAQuads """
        faces = []
        for key, voxel in self.voxels.items():
            self._get_obj_faces(voxel, faces)
        return faces

    def _get_obj_faces(self, voxel, out_faces):
        if voxel.colorIndex == 0:
            return []
        sides = self._obj_exposed(voxel)
        if sides[0]:
            f = _get_left_side(voxel)
            _get_obj_faces_support(0, voxel.colorIndex, f, out_faces)
        if sides[1]:
            f = _get_right_side(voxel)
            _get_obj_faces_support(1, voxel.colorIndex, f, out_faces)
        if sides[2]:
            f = _get_top_side(voxel)
            _get_obj_faces_support(2, voxel.colorIndex, f, out_faces)
        if sides[3]:
            f = _get_bottom_side(voxel)
            _get_obj_faces_support(3, voxel.colorIndex, f, out_faces)
        if sides[4]:
            f = _get_front_side(voxel)
            _get_obj_faces_support(4, voxel.colorIndex, f, out_faces)
        if sides[5]:
            f = _get_back_side(voxel)
            _get_obj_faces_support(5, voxel.colorIndex, f, out_faces)
        return

    def _obj_exposed(self, voxel):
        """ --> a set of [0, 6) representing which voxel faces are shown
            for the meaning of 0-5, see AAQuad.normals
            get the sick truth about these voxels' dirty secrets...
        """
        # check left 0
        side = self.get_voxel(voxel.x - 1, voxel.y, voxel.z)
        s0 = side is None or side.colorIndex == 0
        # check right 1
        side = self.get_voxel(voxel.x + 1, voxel.y, voxel.z)
        s1 = side is None or side.colorIndex == 0
        # check top 2
        side = self.get_voxel(voxel.x, voxel.y, voxel.z + 1)
        s2 = side is None or side.colorIndex == 0
        # check bottom 3
        side = self.get_voxel(voxel.x, voxel.y, voxel.z - 1)
        s3 = side is None or side.colorIndex == 0
        # check front 4
        side = self.get_voxel(voxel.x, voxel.y - 1, voxel.z)
        s4 = side is None or side.colorIndex == 0
        # check back 5
        side = self.get_voxel(voxel.x, voxel.y + 1, voxel.z)
        s5 = side is None or side.colorIndex == 0
        return s0, s1, s2, s3, s4, s5


class Voxel:
    def __init__(self, x, y, z, color_index):
        self.x = x
        self.y = y
        self.z = z
        self.colorIndex = color_index


def gen_normals(self, aa_quads, overwrite=False):
    # compute CCW normal if it doesn't exist
    for face in aa_quads:
        if overwrite or face.normal is None:
            side_a = (face.vertices[1][0] - face.vertices[0][0],
                      face.vertices[1][1] - face.vertices[0][1],
                      face.vertices[1][2] - face.vertices[0][2])
            side_b = (face.vertices[-1][0] - face.vertices[0][0],
                      face.vertices[-1][1] - face.vertices[0][1],
                      face.vertices[-1][2] - face.vertices[0][2])
            # compute the cross product
            face.normal = (side_a[1] * side_b[2] - side_a[2] * side_b[1],
                           side_a[2] * side_b[0] - side_a[0] * side_b[2],
                           side_a[0] * side_b[1] - side_a[1] * side_b[0])


def import_obj(stream):
    vertices = []
    faces = []
    uvs = []
    normals = []
    for line in stream:
        fixed_line = line.strip().split(' ')
        line_type = fixed_line[0].strip()
        data = fixed_line[1:]
        if line_type == 'v':
            # vertex
            v = tuple(map(float, data))
            vertices.append(v)
        elif line_type == 'vt':
            # uv
            uvs.append(tuple(map(float, data)))
        elif line_type == 'vn':
            # normal
            normals.append(tuple(map(float, data)))
        elif line_type == 'f':
            # face (assume all verts/uvs/normals have been processed)
            face_verts = []
            face_uvs = []
            face_normals = []
            for v in data:
                result = v.split('/')
                log.info(result)
                # recall that everything is 1 indexed...
                face_verts.append(vertices[int(result[0]) - 1])
                if len(result) == 1:
                    continue  # there is only a vertex index
                if result[1] != '':
                    # uvs may not be present, ex: 'f vert//normal ...'
                    face_uvs.append(uvs[int(result[1]) - 1])
                if len(result) <= 2:
                    # don't continue if only vert and uv are present
                    continue
                face_normals.append(normals[int(result[2]) - 1])
            faces.append(GeoFace(face_verts, face_uvs, face_normals))
        else:
            # there could be material specs, smoothing, or comments... ignore!
            pass
    return faces


def make_new_texture(old_texture_file, out_file):
    extension = os.path.splitext(old_texture_file)[1].lower()
    if extension != ".png":
        raise ValueError("Invalid texture input %s. Must be PNG file." % old_texture_file)
    new_texture_file = os.path.splitext(out_file)[0] + ".png"
    try:
        shutil.copy(old_texture_file, new_texture_file)
        return new_texture_file
    except Exception as exc:
        log.error("Error during texture copy.")
        raise exc


def make_mtl_file(texture_file, out_file):
    new_mtl_file = out_file + ".mtl"
    texture_file = os.path.split(texture_file)[1]
    with open(new_mtl_file, mode='w') as mtl_stream:
        mtl_stream.write("# https://gitlab.com/Claytone\n\n")
        mtl_stream.write("newmtl palette\nillum 1\n")
        mtl_stream.write("Ka 0.000 0.000 0.000\n")
        mtl_stream.write("Kd 1.000 1.000 1.000\n")
        mtl_stream.write("Ks 0.000 0.000 0.000\n")
        mtl_stream.write("map_Kd %s" % texture_file)
    return new_mtl_file


def convert_to_obj(in_file, out_file, texture_file=None):
    generated_files = []
    log.info(f"Exporting {out_file} ... ")
    export_start_time = time.time()
    with open(in_file, mode='rb') as in_file_stream:
        aa_quads = import_vox_file(in_file_stream).to_quads()
    out_file = os.path.abspath(out_file)
    if texture_file:
        new_texture_file = make_new_texture(texture_file, out_file)
        generated_files.append(new_texture_file)
        mtl_file_name = make_mtl_file(new_texture_file, out_file)
        generated_files.append(mtl_file_name)

    # faces = optimized_greedy_mesh(aa_quads)
    faces = aa_quads
    # copy the normals from AAQuad (99% of cases will use all directions)
    normals = list(AAQuad.normals)
    uvs = set()
    for f in faces:
        if f.uv is not None:
            uvs.add(f.uv)

    uvs = list(uvs)
    f_lines = []
    vertices = []
    index_offset = 1  # recall that OBJ files are 1 indexed
    for f in faces:
        n = 1 + normals.index(f.normal) if f.normal is not None else ''
        uv = 1 + uvs.index(f.uv) if f.uv is not None else ''

        f_line = ["f"]
        for vert in f.vertices:
            try:
                v = 1 + vertices.index(vert)
            except ValueError:
                v = index_offset
                vertices.append(vert)
                index_offset += 1
            f_line.append("/".join(map(str, [v, uv, n])))

        f_lines.append(' '.join(f_line) + '\n')
    with open(out_file, mode='w') as out_file_stream:
        out_file_stream.write('# shivshank\'s .obj optimizer\n')
        if texture_file:
            out_file_stream.write('# Material functionality by Claytone\n')
            out_file_stream.write('\n')
            out_file_stream.write("# material\n")
            out_file_stream.write("mtllib %s\n" % mtl_file_name)
            out_file_stream.write("usemtl palette\n")
        out_file_stream.write('\n')
        if len(normals) > 0:
            out_file_stream.write('# normals\n')
            for n in normals:
                out_file_stream.write('vn ' + ' '.join(list(map(str, n))) + '\n')
            out_file_stream.write('\n')
        if len(uvs) > 0:
            out_file_stream.write('# texcoords\n')
            for i in uvs:
                out_file_stream.write('vt ' + ' '.join(list(map(str, i))) + '\n')
            out_file_stream.write('\n')
        out_file_stream.write('# verts\n')
        for v in vertices:
            out_file_stream.write('v ' + ' '.join(list(map(str, v))) + '\n')
        out_file_stream.write('\n')
        out_file_stream.write('# faces\n')
        for i in f_lines:
            out_file_stream.write(i)
        out_file_stream.write('\n')
        out_file_stream.write('\n')
    export_end_time = time.time()
    log.debug(f"Finished in { export_end_time - export_start_time} seconds")
    generated_files.append(out_file)
    return generated_files


def import_vox_file(file):
    """ --> a VoxelStruct from this .vox file stream """
    vox = VoxelStruct()
    magic = file.read(4)
    #if magic != b'VOX ':
    #    log.info('magic number is', magic)
    #    if user_aborts('This does not appear to be a VOX file. Abort?'):
    #        raise ValueError("Invalid magic number")
    # the file appears to use little endian consistent with RIFF
    version = int.from_bytes(file.read(4), byteorder='little')
    if version != 150:
        print(version)
    #    if user_aborts('Only version 150 is supported; this file: '
    #                   + str(version) + '. Abort?'):
    #        raise ValueError("Invalid file version")
    main_header = _read_chunk_header(file)
    print(main_header)
    if main_header['id'] != b'MAIN':
        if user_aborts('Did not find the main chunk. Abort?'):
            raise ValueError("Did not find main VOX chunk. ")
    # we don't need anything from the size or palette header!
    # : we can figure out (minimum) bounds later from the voxel data
    # : we only need UVs from voxel data; user can export palette elsewhere
    next_header = _read_chunk_header(file)
    while next_header['id'] != b'XYZI':
        # skip the contents of this header and its children, read the next one
        file.read(next_header['size'] + next_header['children_size'])
        next_header = _read_chunk_header(file)
    voxel_header = next_header
    assert voxel_header['id'] == b'XYZI', 'this should be literally impossible'
    assert voxel_header['children_size'] == 0, 'why voxel chunk have children?'
    seek_pos = file.tell()
    total_voxels = int.from_bytes(file.read(4), byteorder='little')
    # READ THE VOXELS #
    for i in range(total_voxels):
        # n.b., byte order should be irrelevant since these are all 1 byte
        x = int.from_bytes(file.read(1), byteorder='little')
        y = int.from_bytes(file.read(1), byteorder='little')
        z = int.from_bytes(file.read(1), byteorder='little')
        color = int.from_bytes(file.read(1), byteorder='little')
        vox.set_voxel(Voxel(x, y, z, color))
    # assert that we've read the entire voxel chunk
    assert file.tell() - seek_pos == voxel_header['size']
    # (there may be more chunks after this but we don't need them!)
    return vox


def _read_chunk_header(buffer):
    chunk_id = buffer.read(4)
    if chunk_id == b'':
        raise ValueError("Unexpected EOF, expected chunk header")
    size = int.from_bytes(buffer.read(4), byteorder='little')
    children_size = int.from_bytes(buffer.read(4), byteorder='little')
    return {
        'id': chunk_id, 'size': size, 'children_size': children_size
    }


def user_aborts(msg):
    log.info(msg + ' (y/n)')
    u = input()
    if u.startswith('n'):
        return False

    return True

