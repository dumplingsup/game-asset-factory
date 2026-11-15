"""Explicit Blender authoring on licensed KAI + Kenney sources; not a generator backend.

Retains original mesh/rest rig/weights/actions and records genuinely added equipment
and facial shape keys. Run with factory-startup/disable-autoexec and inspect results.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True, help='Validated original KAI editable.blend')
parser.add_argument('--equipment-dir', type=Path, required=True)
parser.add_argument('--plan', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
if (out/'kai_prepared.blend').exists():
    raise RuntimeError('Choose a new authoring output directory')
plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def action_fingerprint(action):
    return digest([[c.data_path,c.array_index,[[*p.co,p.interpolation] for p in c.keyframe_points]]
        for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves])


def material_fingerprint(material):
    nodes=[]
    for node in material.node_tree.nodes:
        inputs=[]
        for socket in node.inputs:
            if not hasattr(socket,'default_value'):
                continue
            value=socket.default_value
            if isinstance(value,(str,float,int,bool)):
                inputs.append([socket.identifier,value])
            elif hasattr(value,'__len__'):
                inputs.append([socket.identifier,list(value)])
        image=getattr(node,'image',None)
        image_sha=sha(Path(bpy.path.abspath(image.filepath))) if image and not image.packed_file else hashlib.sha256(bytes(image.packed_file.data)).hexdigest() if image else None
        nodes.append([node.name,node.bl_idname,inputs,image_sha])
    links=sorted([l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier] for l in material.node_tree.links)
    return digest([sorted(nodes),links,material.use_backface_culling,list(material.diffuse_color)])


bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()),load_ui=False,use_scripts=False)
bpy.context.preferences.filepaths.save_version = 0
body = bpy.data.objects['geometry_0']
rig = next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
before_actions = {a.name:action_fingerprint(a) for a in bpy.data.actions}
original_positions = digest([list(v.co) for v in body.data.vertices])
original_weights = digest([[[g.group,g.weight] for g in v.groups] for v in body.data.vertices])
original_uv = digest([[layer.name,[list(p.uv) for p in layer.data]] for layer in body.data.uv_layers])
original_bones = digest([[b.name,b.parent.name if b.parent else None,list(map(list,b.matrix_local))] for b in rig.data.bones])
pose = bpy.data.actions['T-Pose']
rig.animation_data.action = pose
rig.animation_data.action_slot = pose.slots[0]
bpy.context.scene.frame_set(0)
canonical = bpy.data.objects['GAF_Canonical']
canonical.matrix_world = Matrix.Rotation(math.radians(plan['orientation_z_degrees']),4,'Z') @ canonical.matrix_world
bpy.context.view_layer.update()
group = body.vertex_groups[plan['head_group']]
body.shape_key_add(name='Basis')
shape_records = []
surface_groups = {}
for vertex in body.data.vertices:
    point = body.matrix_world @ vertex.co
    surface_groups.setdefault(tuple(round(x,6) for x in point),[]).append(vertex.index)
for spec in plan['face_shapes']:
    key = body.shape_key_add(name=spec['name'], from_mix=False)
    key.relative_key = body.data.shape_keys.reference_key
    key.value = 0
    selected = []
    max_delta = 0.0
    for ids in surface_groups.values():
        weight = max((g.weight for index in ids for g in body.data.vertices[index].groups if g.group==group.index),default=0)
        if weight <= 0:
            continue
        position = body.matrix_world @ body.data.vertices[ids[0]].co
        taper = 1.0
        for axis,bounds in spec['bounds'].items():
            coordinate = position['xyz'.index(axis)]
            edge = (bounds[1]-bounds[0])*0.25
            value = max(0,min(1,(coordinate-bounds[0])/edge,(bounds[1]-coordinate)/edge))
            taper *= value*value*(3-2*value)
        influence = max(math.exp(-0.5*sum(((position[i]-center[i])/spec['sigma'][i])**2 for i in range(3))) for center in spec['centers'])
        influence *= taper * weight
        if influence < 0.001:
            continue
        world_delta = Vector(spec['delta_m']) * influence
        delta = body.matrix_world.to_3x3().inverted() @ world_delta
        for index in ids:
            key.data[index].co += delta
            selected.append(index)
        max_delta = max(max_delta,world_delta.length)
    if not 20 < len(selected) < len(body.data.vertices)*0.2:
        raise RuntimeError('Facial sculpt selection is empty or not a bounded face region')
    shape_records.append({'name':spec['name'],'authored_this_iteration':True,'selected_vertex_ids':selected,
                           'changed_vertices':len(selected),'max_world_delta_m':max_delta,
                           'smooth_bounds_taper':True,'coincident_vertex_displacements_shared':True})
if plan.get('animate_expressions'):
    for index,spec in enumerate(plan['face_shapes']):
        key = body.data.shape_keys.key_blocks[spec['name']]
        peak = 20 + index*20
        for frame,value in ((0,0),(max(0,peak-20),0),(peak,1),(min(60,peak+20),0),(60,0)):
            key.value=value
            key.keyframe_insert(data_path='value',frame=frame,group=key.name)
        key.value=0
    expression_action = body.data.shape_keys.animation_data.action
    expression_action.name='Face_Expressions'
    for layer in expression_action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation='LINEAR'

equipment_records=[]
shared_materials={}
deduplicated_materials=[]
for spec in plan['equipment']:
    source=(args.equipment_dir/spec['file']).resolve()
    existing=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(source))
    imported=set(bpy.data.objects)-existing
    meshes=[o for o in imported if o.type=='MESH']
    if not meshes:
        raise RuntimeError('Equipment import has no actual mesh')
    for mesh in meshes:
        for slot in mesh.material_slots:
            if not slot.material:
                continue
            key=material_fingerprint(slot.material)
            if key in shared_materials:
                deduplicated_materials.append({'original':slot.material.name,'shared':shared_materials[key].name,'reason':'Identical imported shader graph, inputs and image bytes'})
                slot.material=shared_materials[key]
            else:
                shared_materials[key]=slot.material
    points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    lo=Vector([min(v[i] for v in points) for i in range(3)])
    hi=Vector([max(v[i] for v in points) for i in range(3)])
    if hi.z-lo.z<=0:
        raise RuntimeError('Equipment has no vertical extent')
    root=bpy.data.objects.new(spec['node'],None)
    bpy.context.scene.collection.objects.link(root)
    for obj in [o for o in imported if o.parent not in imported]:
        transform=obj.matrix_world.copy();obj.parent=root;obj.matrix_world=transform
    factor=spec['height_m']/(hi.z-lo.z)
    grip=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z+(hi.z-lo.z)*spec['grip_height_fraction']))
    anchor=(rig.matrix_world@rig.pose.bones[spec['bone']].matrix).translation+Vector(spec['offset_m'])
    root.parent=rig;root.parent_type='BONE';root.parent_bone=spec['bone']
    root.matrix_world=Matrix.Translation(anchor) @ Matrix.Rotation(math.radians(spec['rotation_z_degrees']),4,'Z') @ Matrix.Diagonal((factor,factor,factor,1)) @ Matrix.Translation(-grip)
    bpy.context.view_layer.update()
    root['gaf_equipment_slot']=spec['slot']
    root['gaf_equipment_variant']=spec['variant']
    root['gaf_active_scale']=list(root.scale)
    root['gaf_default_active']=spec['default_active']
    equipment_records.append({'node':root.name,'variant':spec['variant'],'slot':spec['slot'],'bone':spec['bone'],
        'source_name':source.name,'source_sha256':sha(source),'mesh_names':[m.name for m in meshes],
        'active_scale':list(root.scale),'default_active':spec['default_active']})

# Ask the actual exporter for bind-space TRS. Keep every source transform invertible;
# slot activation belongs to the component manifest, never a zero-scale source node.
# This is an authoring intermediate, not a build.
helpers={p.custom_shape for p in rig.pose.bones if p.custom_shape}
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.scene.objects:
    if obj not in helpers and obj.type in ('MESH','ARMATURE','EMPTY'):
        obj.select_set(True)
bpy.context.view_layer.objects.active=rig
bind_reference=out/'equipment_bind_reference.glb'
bpy.ops.export_scene.gltf(filepath=str(bind_reference),export_format='GLB',use_selection=True,
    export_apply=False,export_skins=True,export_animations=True,export_animation_mode='ACTIONS',
    export_morph=True,export_morph_animation=True,export_anim_slide_to_zero=False,
    export_cameras=False,export_lights=False,export_def_bones=False,export_force_sampling=True)
import struct
reference_bytes=bind_reference.read_bytes()
reference_json=json.loads(reference_bytes[20:20+struct.unpack_from('<I',reference_bytes,12)[0]])
reference_nodes={n.get('name'):n for n in reference_json['nodes']}
for record in equipment_records:
    node=reference_nodes[record['node']]
    root=bpy.data.objects[record['node']]
    root['gaf_active_scale_gltf']=node.get('scale',[1,1,1])
    root['gaf_active_rotation_gltf']=node.get('rotation',[0,0,0,1])
    record['exporter_bind_scale']=list(root['gaf_active_scale_gltf'])
    record['exporter_bind_rotation']=list(root['gaf_active_rotation_gltf'])

bpy.context.scene.frame_set(0)
bpy.context.view_layer.update()
for key in body.data.shape_keys.key_blocks:
    key.value=0
preserved={'original_base_vertices':original_positions==digest([list(v.co) for v in body.data.vertices]),
    'original_skin_weights':original_weights==digest([[[g.group,g.weight] for g in v.groups] for v in body.data.vertices]),
    'original_uv':original_uv==digest([[layer.name,[list(p.uv) for p in layer.data]] for layer in body.data.uv_layers]),
    'original_rest_rig':original_bones==digest([[b.name,b.parent.name if b.parent else None,list(map(list,b.matrix_local))] for b in rig.data.bones]),
    'all_original_action_curves':all(before_actions[name]==action_fingerprint(bpy.data.actions[name]) for name in before_actions)}
if not all(preserved.values()):
    raise RuntimeError('Authoring changed protected original source data: '+str(preserved))
for image in bpy.data.images:
    if image.source=='FILE' and not image.packed_file:
        image.pack()
target=out/'kai_prepared.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(target))
report={'schema_version':1,'source_blend_sha256':sha(args.source),'authoring_plan_sha256':sha(args.plan),
    'authoring_script_sha256':sha(Path(__file__)),'output_blend_sha256':sha(target),
    'original_clips':sorted(before_actions),'added_clips':['Face_Expressions'] if plan.get('animate_expressions') else [],
    'equipment_bind_reference_sha256':sha(bind_reference),'material_deduplication':deduplicated_materials,
    'added_shapes':shape_records,'added_equipment':equipment_records,'preserved':preserved,'visual_review':'pending_human'}
(out/'authoring_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print('[KAI_AUTHORING]',json.dumps({'output':str(target),'preserved':preserved,'shapes':[(k['name'],k['changed_vertices']) for k in shape_records],'equipment':len(equipment_records)}))
