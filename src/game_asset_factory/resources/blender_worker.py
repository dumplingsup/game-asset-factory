"""Run only inside Blender, with factory startup and automatic scripts disabled."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

request = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
recipe = request['recipe']
output = Path(request['output'])
output.mkdir(parents=True, exist_ok=True)
version = '.'.join(map(str, bpy.app.version))
if version != recipe['blender_version']:
    raise RuntimeError(f'Expected Blender {recipe["blender_version"]}, got {version}')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.preferences.filepaths.save_version = 0


def load_model(path):
    suffix = path.suffix.lower()
    if suffix == '.blend':
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            names = recipe['objects'] or list(src.objects)
            if any(name not in src.objects for name in names):
                raise RuntimeError('Requested object missing from .blend')
            dst.objects = names
        for obj in dst.objects:
            if obj is not None:
                bpy.context.collection.objects.link(obj)
    elif suffix in ('.glb', '.gltf'):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == '.obj':
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        raise RuntimeError('Unsupported import format')


load_model(Path(request['model'] if request['action'] == 'inspect' else request['source']))
objects = list(bpy.context.scene.objects)
if request['action'] == 'build':
    # Static base explicitly refuses silent destruction of animation or skin.
    for obj in objects:
        if obj.type == 'ARMATURE' or obj.animation_data or any(m.type == 'ARMATURE' for m in obj.modifiers) or (obj.type == 'MESH' and obj.data.shape_keys):
            raise RuntimeError('Static profile refuses rigs/animation/morphs; use a future specialized plugin')
    if Path(request['source']).suffix.lower() != '.blend' and recipe['objects']:
        if any(name not in bpy.context.scene.objects for name in recipe['objects']):
            raise RuntimeError('Requested imported object missing')
        objects = [o for o in objects if o.name in recipe['objects']]
    meshes = [o for o in objects if o.type == 'MESH']
    if not meshes:
        raise RuntimeError('No mesh selected')
    for obj in meshes:
        for modifier in obj.modifiers:
            if modifier.type in ('MULTIRES', 'SUBSURF'):
                modifier.levels = min(recipe['subdivision_level'], getattr(modifier, 'total_levels', 2))
                modifier.render_levels = modifier.levels
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    baked = []
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
        rotation = Matrix.Rotation(math.radians(recipe.get('rotation_z_degrees', 0)), 4, 'Z')
        mesh.transform(rotation @ obj.matrix_world)
        target = bpy.data.objects.new('FactoryMesh_' + obj.name, mesh)
        bpy.context.collection.objects.link(target)
        baked.append(target)
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    meshes = baked
    coordinates = [v.co for o in meshes for v in o.data.vertices]
    lo = Vector([min(v[i] for v in coordinates) for i in range(3)])
    hi = Vector([max(v[i] for v in coordinates) for i in range(3)])
    if hi.z - lo.z < 1e-8:
        raise RuntimeError('Zero model height')
    scale = recipe['height_m'] / (hi.z - lo.z)
    transform = Matrix.Diagonal((scale, scale, scale, 1.0)) @ Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
    for obj in meshes:
        obj.data.transform(transform)
        obj.data.update()
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    for image in bpy.data.images:
        if image.source == 'FILE' and not image.packed_file:
            image_path = Path(bpy.path.abspath(image.filepath))
            if not image_path.is_file():
                raise RuntimeError('Missing external texture: ' + str(image_path))
            image.pack()
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'editable.blend'))
    bpy.ops.export_scene.gltf(filepath=str(output / 'model.glb'), export_format='GLB', use_selection=True,
        export_apply=True, export_animations=False, export_skins=False, export_morph=False,
        export_cameras=False, export_lights=False, export_yup=True, export_extras=False)
else:
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']

if not meshes:
    raise RuntimeError('No imported mesh')
vertices = []
triangles = quads = non_manifold = loose = 0
for obj in meshes:
    mesh = obj.data
    mesh.calc_loop_triangles()
    triangles += len(mesh.loop_triangles)
    quads += sum(len(p.vertices) == 4 for p in mesh.polygons)
    vertices.extend(obj.matrix_world @ v.co for v in mesh.vertices)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    non_manifold += sum(not e.is_manifold for e in bm.edges)
    loose += sum(not v.link_edges for v in bm.verts)
    bm.free()
if not all(math.isfinite(value) for point in vertices for value in point):
    raise RuntimeError('Non-finite mesh positions')
report = {'version': version, 'action': request['action'], 'mesh_objects': len(meshes), 'vertices': len(vertices),
    'polygons': sum(len(o.data.polygons) for o in meshes), 'triangles_evaluated': triangles, 'quads': quads,
    'non_manifold_edges': non_manifold, 'loose_vertices': loose,
    'uv_layers': {o.name: len(o.data.uv_layers) for o in meshes},
    'bounds_blender_z_up': {'min': [min(v[i] for v in vertices) for i in range(3)], 'max': [max(v[i] for v in vertices) for i in range(3)]},
    'materials': sorted({m.name for o in meshes for m in o.data.materials if m}),
    'images': [{'name': i.name, 'size': list(i.size), 'packed': bool(i.packed_file)} for i in bpy.data.images],
    'visual_review': 'pending_human', 'limits': 'Static geometry and import metrics; does not approve aesthetics or evaluate self-intersections/rig deformation'}
(output / 'blender_report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
print('[GAF]', json.dumps(report))
