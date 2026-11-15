"""Blender-only diagnostic; reads the licensed Fox without changing the raw file."""
import bpy
import json
from pathlib import Path
import sys

root = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
source = next((root / 'vendor/khronos-fox').glob('*/*.glb'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(source))
report = {'objects': [], 'actions': []}
for obj in bpy.context.scene.objects:
    row = {'name': obj.name, 'type': obj.type, 'parent': obj.parent.name if obj.parent else None,
           'scale': list(obj.scale), 'location': list(obj.location), 'dimensions': list(obj.dimensions)}
    if obj.type == 'ARMATURE':
        row['bones'] = [{'name': b.name, 'head': list(b.head_local), 'tail': list(b.tail_local)} for b in obj.data.bones]
        row['nla'] = [{'name': t.name, 'strips': [s.action.name for s in t.strips if s.action]} for t in obj.animation_data.nla_tracks]
    if obj.type == 'MESH':
        row['groups'] = [g.name for g in obj.vertex_groups]
        row['bounds'] = {'min': [min(v.co[i] for v in obj.data.vertices) for i in range(3)], 'max': [max(v.co[i] for v in obj.data.vertices) for i in range(3)]}
        row['vertices'] = len(obj.data.vertices)
    report['objects'].append(row)
for action in bpy.data.actions:
    report['actions'].append({'name': action.name, 'frame_range': list(action.frame_range), 'slots': [s.identifier for s in action.slots]})
out = root / 'artifacts/v02/probe'
out.mkdir(parents=True, exist_ok=True)
(out / 'fox.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
