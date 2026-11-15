"""Blender character import/edit/export preserving the actual rig and actions."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_integrity import compare_morph_geometry

request = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
recipe = request['recipe']
output = Path(request['output'])
output.mkdir(parents=True, exist_ok=True)
version = '.'.join(map(str, bpy.app.version))
if version != recipe['blender_version']:
    raise RuntimeError('Blender version differs from recipe')


def dump(name, data):
    (output / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load(path):
    if path.suffix.lower() == '.blend':
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    else:
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.scene.render.fps = recipe['animation_fps']
        if path.suffix.lower() in ('.glb', '.gltf'):
            bpy.ops.import_scene.gltf(filepath=str(path))
        elif path.suffix.lower() == '.fbx':
            bpy.ops.import_scene.fbx(filepath=str(path))
        else:
            raise RuntimeError('Character importer supports .blend, .glb/.gltf and .fbx')
    bpy.context.preferences.filepaths.save_version = 0


def scene_objects():
    rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    helpers = {p.custom_shape for r in rigs for p in r.pose.bones if p.custom_shape}
    objects = [o for o in bpy.context.scene.objects if o not in helpers and o.type in ('MESH', 'ARMATURE', 'EMPTY')]
    meshes = [o for o in objects if o.type == 'MESH']
    if not rigs or not meshes or not bpy.data.actions:
        raise RuntimeError('A real armature, mesh and animation action are required')
    if any(o.data.shape_keys for o in meshes) and recipe.get('morph_targets', 'reject') != 'preserve':
        raise RuntimeError('Morph targets require explicit morph_targets=preserve; refusing silent loss')
    bone_names = {b.name for r in rigs for b in r.data.bones}
    if any(sum(g.weight > 0 and mesh.vertex_groups[g.group].name in bone_names for g in v.groups) > 4 for mesh in meshes for v in mesh.data.vertices):
        raise RuntimeError('Verified profile supports four bone influences per vertex; refusing silent truncation')
    return objects, meshes, rigs


def curves(action):
    result = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    result.append([curve.data_path, curve.array_index,
                                   [[float(p.co.x), float(p.co.y), p.interpolation] for p in curve.keyframe_points]])
    return sorted(result, key=lambda row: (row[0], row[1]))


def snapshot():
    objects, meshes, rigs = scene_objects()
    bones = [[r.name, b.name, b.parent.name if b.parent else None, [list(row) for row in b.matrix_local]] for r in rigs for b in r.data.bones]
    weights = {m.name: [[[m.vertex_groups[g.group].name, float(g.weight)] for g in v.groups] for v in m.data.vertices] for m in meshes}
    uv = {m.name: {layer.name: [list(loop.uv) for loop in layer.data] for layer in m.data.uv_layers} for m in meshes}
    materials = {}
    for material in {slot.material for obj in meshes for slot in obj.material_slots if slot.material}:
        nodes = []
        links = []
        if material.use_nodes:
            for node in material.node_tree.nodes:
                defaults = []
                for socket in node.inputs:
                    if not hasattr(socket, 'default_value'):
                        continue
                    value = socket.default_value
                    if isinstance(value, (float, int, str, bool)):
                        defaults.append([socket.identifier, value])
                    elif hasattr(value, '__len__'):
                        defaults.append([socket.identifier, list(value)])
                nodes.append([node.name, node.bl_idname, node.image.name if hasattr(node, 'image') and node.image else None, defaults])
            links = sorted([l.from_node.name, l.from_socket.identifier, l.to_node.name, l.to_socket.identifier] for l in material.node_tree.links)
        materials[material.name] = {'nodes': sorted(nodes), 'links': links}
    images = [{'name': image.name, 'size': list(image.size), 'colorspace': image.colorspace_settings.name,
               'packed_sha256': hashlib.sha256(bytes(image.packed_file.data)).hexdigest() if image.packed_file else None} for image in bpy.data.images if image.source != 'VIEWER']
    actions = [{'name': action.name, 'frame_range': list(action.frame_range),
                'export_frame_range': [min(0.0, action.frame_range[0]), action.frame_range[1]],
                'channels': len(curves(action)), 'sha256': digest(curves(action))} for action in bpy.data.actions]
    morphs = {m.name: [{'name': key.name, 'relative_to': key.relative_key.name,
                       'delta': [[round(x, 6) for x in (p.co-b.co)] for p,b in zip(key.data,key.relative_key.data,strict=True)]}
                      for key in m.data.shape_keys.key_blocks if key != m.data.shape_keys.reference_key]
              for m in meshes if m.data.shape_keys}
    vertices = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    for mesh in meshes:
        mesh.data.calc_loop_triangles()
    return {'version': version, 'mesh_objects': len(meshes), 'vertices': sum(len(o.data.vertices) for o in meshes),
            'triangles_evaluated': sum(len(o.data.loop_triangles) for o in meshes),
            'armatures': len(rigs), 'bones': sum(len(r.data.bones) for r in rigs),
            'skinned_meshes': sum(any(mod.type == 'ARMATURE' for mod in o.modifiers) for o in meshes),
            'bones_sha256': digest(bones), 'weights_sha256': digest(weights), 'uv_sha256': digest(uv),
            'actions_sha256': digest(actions), 'materials_sha256': digest(materials), 'images_sha256': digest(images),
            'morphs_sha256': digest(morphs), 'morph_targets': {name:[k['name'] for k in keys] for name,keys in morphs.items()},
            'actions': actions, 'images': images,
            'mesh_names': [o.name for o in meshes], 'bone_names': [b.name for r in rigs for b in r.data.bones],
            'bounds_blender_z_up': {'min': [min(v[i] for v in vertices) for i in range(3)], 'max': [max(v[i] for v in vertices) for i in range(3)]},
            'visual_review': 'pending_human'}


def morph_geometry():
    result = {}
    for mesh in scene_objects()[1]:
        if not mesh.data.shape_keys:
            continue
        keys = [k for k in mesh.data.shape_keys.key_blocks if k != mesh.data.shape_keys.reference_key]
        basis = mesh.data.shape_keys.reference_key
        if mesh.data.name in result:
            raise RuntimeError('Instanced morph data needs explicit instance correspondence')
        result[mesh.data.name] = {'names':[k.name for k in keys],
            'positions':[list(mesh.matrix_world @ v.co) for v in basis.data],
            'deltas':[[list(mesh.matrix_world.to_3x3() @ (p.co-b.co)) for p,b in zip(k.data,k.relative_key.data,strict=True)] for k in keys]}
    return result


def components():
    return {'schema_version':1, 'equipment':[{'node':o.name,
                'slot':o['gaf_equipment_slot'], 'variant':o['gaf_equipment_variant'],
                'attachment_bone':o.parent_bone if o.parent_type=='BONE' else None,
                'active_scale':list(o.get('gaf_active_scale_gltf',o['gaf_active_scale'])),
                'active_rotation':list(o.get('gaf_active_rotation_gltf',[0,0,0,1])),
                'default_active':bool(o.get('gaf_default_active',True))}
              for o in scene_objects()[0] if 'gaf_equipment_slot' in o]}


source = Path(request['model'] if request['action'] in ('inspect', 'edit') else request['source'])
load(source)
before = snapshot()
dump('input_snapshot.json', before)
objects, meshes, rigs = scene_objects()
if request['action'] == 'build' and recipe['height_m'] is not None:
    canonical = bpy.data.objects.new('GAF_Canonical', None)
    bpy.context.collection.objects.link(canonical)
    for obj in [o for o in objects if o.parent is None]:
        transform = obj.matrix_world.copy()
        obj.parent = canonical
        obj.matrix_world = transform
    canonical.rotation_euler.z = math.radians(recipe['rotation_z_degrees'])
    bpy.context.view_layer.update()
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector([min(v[i] for v in points) for i in range(3)])
    hi = Vector([max(v[i] for v in points) for i in range(3)])
    if hi.z - lo.z <= 0:
        raise RuntimeError('Invalid character height')
    factor = recipe['height_m'] / (hi.z - lo.z)
    canonical.matrix_world = Matrix.Diagonal((factor, factor, factor, 1)) @ Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)) @ canonical.matrix_world
    bpy.context.view_layer.update()

if request['action'] == 'edit':
    operation = request['operation']
    if operation.get('kind') != 'vertex_offset':
        raise RuntimeError('Unsupported character edit operation')
    obj = next((m for m in meshes if m.name == operation['object']), None)
    if obj is None:
        raise RuntimeError('Edit object not found')
    where = operation['where']
    group = obj.vertex_groups.get(where['vertex_group'])
    if group is None:
        raise RuntimeError('Edit vertex group not found')
    delta = Vector(operation['delta'])
    if len(operation['delta']) != 3 or not all(math.isfinite(v) for v in delta) or delta.length == 0:
        raise RuntimeError('Invalid edit delta')
    original = [v.co.copy() for v in obj.data.vertices]
    selected = []
    deltas = {}
    for vertex in obj.data.vertices:
        weight = next((g.weight for g in vertex.groups if g.group == group.index), 0)
        if weight < where.get('min_weight', 0.5):
            continue
        if all(pair[0] <= vertex.co['xyz'.index(axis)] <= pair[1] for axis, pair in where.get('bounds', {}).items()):
            influence = 1.0
            if operation.get('falloff'):
                falloff = operation['falloff']
                axis = 'xyz'.index(falloff['axis'])
                low,high = falloff['range']
                if not math.isfinite(low) or not math.isfinite(high) or high<=low:
                    raise RuntimeError('Invalid local edit falloff range')
                value = max(0.0,min(1.0,(vertex.co[axis]-low)/(high-low)))
                influence = value*value*(3-2*value)
            if influence<=0:
                continue
            selected.append(vertex.index)
            deltas[vertex.index] = delta * influence
    fraction = len(selected) / len(original)
    if not selected or fraction > operation.get('max_fraction', 0.1):
        raise RuntimeError('Edit selection empty or larger than configured local-region limit')
    original_keys = {key.name:[p.co.copy() for p in key.data] for key in obj.data.shape_keys.key_blocks} if obj.data.shape_keys else {}
    for index in selected:
        obj.data.vertices[index].co = original[index] + deltas[index]
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                key.data[index].co = original_keys[key.name][index] + deltas[index]
    obj.data.update()
    selected_set = set(selected)
    untouched = all(obj.data.vertices[i].co == old for i, old in enumerate(original) if i not in selected_set)
    after = snapshot()
    preserved = {key: before[key] == after[key] for key in ('bones_sha256', 'weights_sha256', 'uv_sha256', 'actions_sha256', 'materials_sha256', 'images_sha256','morphs_sha256')}
    if not untouched or not all(preserved.values()):
        raise RuntimeError('Local edit changed unrelated geometry or protected character data')
    dump('edit_report.json', {'operation': operation, 'selected_vertex_ids': selected, 'vertices_modified': len(selected),
         'total_vertices': len(original), 'unselected_positions_unchanged': untouched, 'preserved': preserved,
         'world_delta_m': list(obj.matrix_world.to_3x3() @ delta), 'before': before, 'after': after,
         'visual_review': 'pending_human'})

if request['action'] != 'inspect':
    for image in bpy.data.images:
        if image.source == 'FILE' and not image.packed_file:
            if not Path(bpy.path.abspath(image.filepath)).is_file():
                raise RuntimeError('Missing external character texture')
            image.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'editable.blend'))
    if request['action'] == 'build':
        dump('morph_reference.json', morph_geometry())
        dump('components.json', components())
        objects, meshes, rigs = scene_objects()
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = rigs[0]
        bpy.ops.export_scene.gltf(filepath=str(output / 'model.glb'), export_format='GLB', use_selection=True,
            export_apply=False, export_skins=True, export_animations=True, export_animation_mode='ACTIONS',
            export_morph=recipe.get('morph_targets','reject')=='preserve', export_morph_normal=True,
            export_morph_animation=True, export_anim_slide_to_zero=False,
            export_cameras=False, export_lights=False, export_extras=False,
            export_def_bones=False, export_force_sampling=True)
report = snapshot()
if request['action'] == 'inspect' and request.get('morph_reference'):
    reference = json.loads(Path(request['morph_reference']).read_text(encoding='utf-8'))
    report['morph_reimport'] = compare_morph_geometry(reference, morph_geometry())
report['action'] = request['action']
dump('blender_report.json', report)
print('[GAF_CHARACTER]', json.dumps({k: report[k] for k in ('action', 'bones', 'skinned_meshes', 'vertices', 'actions')}))
