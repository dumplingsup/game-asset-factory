"""Strict static GLB checks; complemented by real Blender and Godot import."""
import hashlib
import json
import math
from pathlib import Path
import struct


def validate_glb(path):
    raw = Path(path).read_bytes()
    if len(raw) < 28:
        raise ValueError('Truncated GLB')
    magic, version, total = struct.unpack_from('<4sII', raw)
    if magic != b'glTF' or version != 2 or total != len(raw):
        raise ValueError('Invalid GLB header/length')
    chunks, offset = [], 12
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError('Truncated chunk header')
        length, kind = struct.unpack_from('<II', raw, offset)
        offset += 8
        if length % 4 or offset + length > len(raw):
            raise ValueError('Invalid chunk alignment/range')
        chunks.append((kind, raw[offset:offset + length]))
        offset += length
    if len(chunks) != 2 or [c[0] for c in chunks] != [0x4E4F534A, 0x004E4942]:
        raise ValueError('Static profile expects one JSON and one BIN chunk')
    data = json.loads(chunks[0][1], parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
    binary = chunks[1][1]
    if data.get('asset', {}).get('version') != '2.0':
        raise ValueError('Not glTF 2.0')
    if data.get('extensionsRequired'):
        raise ValueError('Required extensions unsupported by static base validator')
    if data.get('skins') or data.get('animations'):
        raise ValueError('Static profile does not support skin/animation')
    buffers = data.get('buffers', [])
    if len(buffers) != 1 or buffers[0].get('uri') or not 0 <= len(binary) - buffers[0]['byteLength'] <= 3:
        raise ValueError('Invalid or external buffer')
    views = data.get('bufferViews', [])
    for v in views:
        if v.get('buffer', 0) != 0 or v.get('byteOffset', 0) < 0 or v.get('byteLength', 0) <= 0 or v.get('byteOffset', 0) + v['byteLength'] > buffers[0]['byteLength']:
            raise ValueError('Buffer view out of range')
    types = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
    widths = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
    accessors = data.get('accessors', [])
    values = []
    for a in accessors:
        if 'sparse' in a or a.get('componentType') not in types or a.get('type') not in widths:
            raise ValueError('Unsupported accessor type/sparse data')
        view_id = a.get('bufferView', -1)
        if not 0 <= view_id < len(views) or not isinstance(a.get('count'), int) or a['count'] <= 0:
            raise ValueError('Invalid accessor reference/count')
        v = views[view_id]
        code, component_size = types[a['componentType']]
        size = component_size * widths[a['type']]
        stride = v.get('byteStride', size)
        start = a.get('byteOffset', 0)
        if start < 0 or stride < size or stride % component_size or start % component_size or start + stride * (a['count'] - 1) + size > v['byteLength']:
            raise ValueError('Accessor range/stride invalid')
        rows = [struct.unpack_from('<' + code * widths[a['type']], binary, v.get('byteOffset', 0) + start + i * stride) for i in range(a['count'])]
        if code == 'f' and any(not math.isfinite(x) for row in rows for x in row):
            raise ValueError('Non-finite vertex data')
        values.append(rows)
    vertices = triangles = degenerate_indices = 0
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    meshes = data.get('meshes', [])
    if not meshes:
        raise ValueError('No meshes')
    primitive_count = 0
    geometry = hashlib.sha256()
    for mesh in meshes:
        for p in mesh.get('primitives', []):
            primitive_count += 1
            if p.get('mode', 4) != 4 or p.get('targets') or p.get('extensions'):
                raise ValueError('Static profile requires uncompressed triangles without morph targets')
            attrs = p.get('attributes', {})
            position_id = attrs.get('POSITION', -1)
            if not 0 <= position_id < len(accessors):
                raise ValueError('Missing POSITION')
            position = accessors[position_id]
            if position['type'] != 'VEC3' or position['componentType'] != 5126:
                raise ValueError('POSITION must be VEC3 float')
            count = position['count']
            for attribute_id in attrs.values():
                if not 0 <= attribute_id < len(accessors) or accessors[attribute_id]['count'] != count:
                    raise ValueError('Attribute count/reference mismatch')
            for row in values[position_id]:
                for axis in range(3):
                    lo[axis], hi[axis] = min(lo[axis], row[axis]), max(hi[axis], row[axis])
            if 'indices' in p:
                idx = p['indices']
                if not 0 <= idx < len(accessors) or accessors[idx]['type'] != 'SCALAR' or accessors[idx]['componentType'] not in (5121, 5123, 5125):
                    raise ValueError('Invalid index accessor')
                indices = [r[0] for r in values[idx]]
            else:
                indices = list(range(count))
            if len(indices) % 3 or any(i >= count for i in indices):
                raise ValueError('Invalid triangle indices')
            quantized = [[0.0 if abs(x) < 0.000005 else round(x, 5) for x in row] for row in values[position_id]]
            geometry.update(json.dumps([quantized, indices], separators=(',', ':')).encode())
            if 'material' in p and not 0 <= p['material'] < len(data.get('materials', [])):
                raise ValueError('Invalid material reference')
            degenerate_indices += sum(len(set(indices[i:i + 3])) != 3 for i in range(0, len(indices), 3))
            vertices += count
            triangles += len(indices) // 3
    if triangles < 1:
        raise ValueError('No triangles')
    for image in data.get('images', []):
        if image.get('uri') or not 0 <= image.get('bufferView', -1) < len(views):
            raise ValueError('Expected embedded image with valid buffer view')
    for node in data.get('nodes', []):
        if 'mesh' in node and not 0 <= node['mesh'] < len(meshes):
            raise ValueError('Invalid node mesh reference')
    semantic = {k: data.get(k) for k in ('meshes', 'nodes', 'materials', 'textures', 'images', 'samplers', 'accessors', 'bufferViews')}
    digest = hashlib.sha256(json.dumps(semantic, sort_keys=True, separators=(',', ':')).encode() + binary).hexdigest()
    return {'format': 'GLB 2.0 static', 'technical_status': 'passed', 'vertices_exported': vertices,
            'triangles_mesh_definitions': triangles, 'meshes': len(meshes), 'primitives': primitive_count,
            'materials': len(data.get('materials', [])), 'embedded_images': len(data.get('images', [])),
            'position_bounds_gltf_local': {'min': lo, 'max': hi}, 'degenerate_index_triangles': degenerate_indices,
            'semantic_sha256': digest, 'geometry_sha256_at_1e_5': geometry.hexdigest(), 'visual_review': 'pending_human',
            'coverage': 'Structural/buffer/accessor/finite/index checks plus Blender reimport; not Khronos certification or visual acceptance'}
