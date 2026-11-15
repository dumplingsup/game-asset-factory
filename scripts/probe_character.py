"""Read-only Blender source survey; never builds assets or grants visual approval.

Legacy invocation with only the factory root still surveys the pinned Fox.
Invoke Blender with --factory-startup --disable-autoexec --python-exit-code 23.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('root', type=Path)
parser.add_argument('--source', type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
root = args.root.resolve()
source = args.source.resolve() if args.source else next((root / 'vendor/khronos-fox').glob('*/*.glb'))
out = args.output.resolve() if args.output else root / 'artifacts/v02/probe'
out.mkdir(parents=True, exist_ok=True)
report_path = out / ('source_probe.json' if args.source else 'fox.json')
if report_path.exists():
    raise RuntimeError('Probe report already exists; choose a new output directory')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


original_hash = sha(source)
container = {}
if source.suffix.lower() in ('.glb', '.vrm'):
    raw = source.read_bytes()
    if raw[:4] != b'glTF':
        raise RuntimeError('Expected binary glTF container')
    size = struct.unpack_from('<I', raw, 12)[0]
    data = json.loads(raw[20:20 + size])
    container = {'asset': data.get('asset'), 'extensions_used': data.get('extensionsUsed', []),
                 'extensions_required': data.get('extensionsRequired', []),
                 'vrm_meta': data.get('extensions', {}).get('VRM', {}).get('meta'),
                 'animation_names': [a.get('name', '') for a in data.get('animations', [])],
                 'mesh_count': len(data.get('meshes', [])), 'material_count': len(data.get('materials', [])),
                 'target_counts': [[len(p.get('targets', [])) for p in m.get('primitives', [])] for m in data.get('meshes', [])]}

bpy.ops.wm.read_factory_settings(use_empty=True)
load_source = source
if source.suffix.lower() == '.vrm':
    # Extension alias only, not a VRM converter. Retain raw input and record the alias.
    load_source = out / 'source_for_gltf_import.glb'
    if load_source.exists():
        raise RuntimeError('Probe import alias already exists')
    shutil.copyfile(source, load_source)
    assert sha(load_source) == original_hash
if source.suffix.lower() == '.blend':
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
elif load_source.suffix.lower() in ('.glb', '.gltf'):
    bpy.ops.import_scene.gltf(filepath=str(load_source))
elif source.suffix.lower() == '.fbx':
    bpy.ops.import_scene.fbx(filepath=str(source))
else:
    raise RuntimeError('Probe accepts .blend/.glb/.gltf/.vrm/.fbx')

rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
helpers = {p.custom_shape for r in rigs for p in r.pose.bones if p.custom_shape}
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o not in helpers]
report = {'schema_version': 1, 'purpose': 'Source survey only; not a build, format-validation receipt or E2E',
          'source_name': source.name, 'source_sha256': original_hash, 'source_bytes': source.stat().st_size,
          'blender_version': bpy.app.version_string, 'container': container, 'meshes': [], 'rigs': [], 'actions': [],
          'visual_review': 'pending_human', 'species_and_equipment_semantics': 'not_inferred_from_counts',
          'vrm_limit': 'glTF fallback inspection only; VRM expressions, MToon, spring bones and runtime semantics are not certified'}
for obj in meshes:
    obj.data.calc_loop_triangles()
    bones = {b.name for mod in obj.modifiers if mod.type == 'ARMATURE' and mod.object for b in mod.object.data.bones}
    influences = [sum(g.weight > 0 and obj.vertex_groups[g.group].name in bones for g in v.groups) for v in obj.data.vertices]
    shapes = []
    if obj.data.shape_keys:
        basis = obj.data.shape_keys.reference_key
        for key in obj.data.shape_keys.key_blocks:
            if key == basis:
                continue
            distances = [(p.co - b.co).length for p, b in zip(key.data, key.relative_key.data, strict=True)]
            shapes.append({'name': key.name, 'relative_to': key.relative_key.name, 'vertices': len(key.data),
                           'changed_vertices': sum(x > 0.000001 for x in distances), 'max_source_delta': max(distances, default=0)})
    report['meshes'].append({'name': obj.name, 'vertices': len(obj.data.vertices), 'triangles': len(obj.data.loop_triangles),
        'materials': [s.material.name if s.material else None for s in obj.material_slots],
        'used_material_slots': sorted({p.material_index for p in obj.data.polygons}),
        'armatures': [mod.object.name for mod in obj.modifiers if mod.type == 'ARMATURE' and mod.object],
        'max_joint_influences': max(influences, default=0), 'unweighted_vertices': sum(x == 0 for x in influences),
        'uv_layers': [layer.name for layer in obj.data.uv_layers], 'morph_targets': shapes,
        'parent': obj.parent.name if obj.parent else None, 'parent_type': obj.parent_type, 'parent_bone': obj.parent_bone})
for obj in rigs:
    report['rigs'].append({'name': obj.name, 'bones': [{'name': b.name, 'parent': b.parent.name if b.parent else None} for b in obj.data.bones]})
for action in bpy.data.actions:
    curves = [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]
    report['actions'].append({'name': action.name, 'frame_range': list(action.frame_range),
        'keyframes': sum(len(c.keyframe_points) for c in curves),
        'bone_channels': sum(c.data_path.startswith('pose.bones[') for c in curves),
        'morph_channels': sum('key_blocks[' in c.data_path for c in curves)})
material_names = {s.material.name for m in meshes for s in m.material_slots if s.material}
report['counts'] = {'meshes': len(meshes), 'materials': len(material_names), 'rigs': len(rigs),
    'bones': sum(len(o.data.bones) for o in rigs), 'actions': len(report['actions']),
    'morph_targets': sum(len(m['morph_targets']) for m in report['meshes'])}
report['readiness_checks'] = {'multiple_meshes': len(meshes) > 1, 'multiple_materials': len(material_names) > 1,
    'has_real_skin': any(m['armatures'] and m['max_joint_influences'] for m in report['meshes']),
    'has_existing_bone_actions': any(a['bone_channels'] and a['keyframes'] > 1 for a in report['actions']),
    'has_nonzero_morphs': any(k['changed_vertices'] for m in report['meshes'] for k in m['morph_targets'])}
if sha(source) != original_hash:
    raise RuntimeError('Raw source changed during read-only probe')
report['raw_source_unchanged'] = True
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
print('[GAF_SOURCE_PROBE]', json.dumps({'report': str(report_path), 'counts': report['counts'], 'readiness_checks': report['readiness_checks']}))
