from typing import Literal

import bpy
import bmesh
from mathutils import Vector

from mathutils.bvhtree import BVHTree

"""
Mode: 
    VERTICAL: Casts vertical (upwards) rays from all faces. If an hit is found, the face gets deleted
    NORMAL: Cast rays into normal direction of the face
Debug:
    If enabled, the mesh will not get modified. All faces that get hit by a ray of a selected face will get selected.
Debug objects:
    If enabled on top of "Debug", the script additionally spawns primitives at the relevant positions:
    
    Default cube: Starting point of ray
    Icosphere: Starting point of ray + direction
    Torus: Intersecting point of ray
"""
MODE = "VERTICAL"  # type: Literal["NORMAL", "VERTICAL"]
RAY_LENGTH = 400
# Debug settings
DEBUG = False
DEBUG_OBJECTS = False

if MODE == "VERTICAL":
    # Offset vector for vertical mode, the starting point of the ray will get offset by this
    vert_offset = Vector((0, 0, 5))
    # Direction array for rays
    vert_vector = Vector((0, 0, 0))
else:
    # For normal mode, the ray will get offset by 10% of the normal vector
    vert_offset = None
    vert_vector = None

########################################################################################################################


def log(*args):
    print("terrain_cleanup:", *args)


log(f"Mode: {MODE}, ray_len: {RAY_LENGTH}, debug: {DEBUG}, create debug objects: {DEBUG}")

# Get active mesh
obj = bpy.context.view_layer.objects.active
mesh = obj.data
mesh_name = obj.name
mat = obj.matrix_world
bpy.ops.object.mode_set(mode="EDIT")

# Find debug faces (selected faces)
if DEBUG:
    debug_faces = []
    for face in mesh.polygons:
        if face.select:
            debug_faces.append(face.index)
    log("Debug faces: ", debug_faces)
else:
    debug_faces = None
to_select = []  # Faces that should get selected
to_create = []  # Objects to create

count_vertex = len(mesh.vertices)
count_edges = len(mesh.edges)
count_faces = len(mesh.polygons)

bm = bmesh.from_edit_mesh(mesh)
my_tree0 = BVHTree.FromBMesh(bm)

if vert_offset:
    # Converting vertical offset to local coordinates
    vert_offset = vert_offset @ mat

i = 0
deleted = 0
log(f"Starting cleanup for {mesh_name} ({count_faces} faces to check)")
bm.faces.ensure_lookup_table()

if MODE == "VERTICAL":
    # Converting vertical direction to local coordinates
    vert_vector = vert_vector @ mat

# noinspection PyTypeChecker
for face in bm.faces:  # type: bmesh.types.BMFace
    i += 1
    # Center of face
    pos = face.calc_center_median()
    # Adjusting position to prevent the ray from intersecting with the emitting face itself
    # and calculating direction for ray
    if MODE == "NORMAL":
        nor = face.normal
        nor.normalize()
        pos = pos + nor * 0.1
    elif MODE == "VERTICAL":
        # Convert to local coordinates
        nor = vert_vector
        pos = pos + vert_offset
    else:
        raise TypeError(f"Unexpected literal for MODE: '{MODE}'")

    # Casting ray
    r_pos, p_nor, p_i, p_dist = my_tree0.ray_cast(pos, nor, RAY_LENGTH)

    if r_pos is not None:
        if not DEBUG:
            bm.faces.remove(face)
            deleted += 1
        else:
            if face.index in debug_faces:
                log(f"Found debug face {i}, hit {p_i}, distance {p_dist:.2f}")
                log(pos, r_pos)
                to_select.append(p_i)
                to_create.append((pos, (pos + nor), r_pos))
    if i % 30000 == 0:
        progress = i/count_faces
        log(f"{progress:4.1%} Processed {i:,} faces, deleted {deleted:,}")

if DEBUG:
    if len(to_select) == 0:
        log("No faces hit")
    else:
        log(f"Selecting faces ", to_select)
        for face in to_select:
            bm.faces[face].select = True
            log(f"Selected face ", face)

bmesh.update_edit_mesh(mesh, destructive=not DEBUG)
if not DEBUG:
    log(f"Deleted {deleted:,} faces, cleaning up mesh (this may take a while, blender might freeze)...")
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete_loose()
if DEBUG_OBJECTS:
    bpy.ops.object.mode_set(mode="OBJECT")
    if DEBUG:
        for pos, p_n, r_pos in to_create:
            bpy.ops.mesh.primitive_cube_add(location=mat @ pos, size=0.5)
            bpy.ops.mesh.primitive_ico_sphere_add(location=mat @ p_n, scale=(0.2, 0.2, 0.2))
            bpy.ops.mesh.primitive_torus_add(location=mat @ r_pos, major_radius=0.5)
log("Cleanup completed")
