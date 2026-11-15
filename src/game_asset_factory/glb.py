"""Strict static GLB checks; complemented by real Blender and Godot import."""
import hashlib
import json
import math
from pathlib import Path
import struct


def validate_glb(path, *, allow_character=False):
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
    if not allow_character and (data.get('skins') or data.get('animations')):
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
    textures = data.get('textures', [])
    material_channels = []
    for material in data.get('materials', []):
        pbr = material.get('pbrMetallicRoughness', {})
        slots = {key: pbr[key] for key in ('baseColorTexture', 'metallicRoughnessTexture') if key in pbr}
        slots.update({key: material[key] for key in ('normalTexture', 'occlusionTexture', 'emissiveTexture') if key in material})
        for slot in slots.values():
            index = slot.get('index', -1)
            if not 0 <= index < len(textures) or not 0 <= textures[index].get('source', -1) < len(data.get('images', [])):
                raise ValueError('Invalid material texture/image reference')
        material_channels.append({'name': material.get('name', ''), 'textures': sorted(slots),
                                  'base_color_factor': pbr.get('baseColorFactor', [1, 1, 1, 1]),
                                  'metallic_factor': pbr.get('metallicFactor', 1), 'roughness_factor': pbr.get('roughnessFactor', 1)})
    for node in data.get('nodes', []):
        if 'mesh' in node and not 0 <= node['mesh'] < len(meshes):
            raise ValueError('Invalid node mesh reference')
    semantic = {k: data.get(k) for k in ('meshes', 'nodes', 'materials', 'textures', 'images', 'samplers', 'accessors', 'bufferViews')}
    if allow_character:
        semantic.update(skins=data.get('skins'), animations=data.get('animations'))
    digest = hashlib.sha256(json.dumps(semantic, sort_keys=True, separators=(',', ':')).encode() + binary).hexdigest()
    result = {'format': 'GLB 2.0 character' if allow_character else 'GLB 2.0 static', 'technical_status': 'passed', 'vertices_exported': vertices,
            'triangles_mesh_definitions': triangles, 'meshes': len(meshes), 'primitives': primitive_count,
            'materials': len(data.get('materials', [])), 'embedded_images': len(data.get('images', [])),
            'material_channels': material_channels,
            'position_bounds_gltf_local': {'min': lo, 'max': hi}, 'degenerate_index_triangles': degenerate_indices,
            'semantic_sha256': digest, 'geometry_sha256_at_1e_5': geometry.hexdigest(), 'visual_review': 'pending_human',
            'coverage': 'Structural/buffer/accessor/finite/index checks plus Blender reimport; not Khronos certification or visual acceptance'}
    if allow_character:
        result.update(character_metrics(data, accessors, values))
    return result


def character_metrics(data, accessors, values):
    nodes, skins = data.get('nodes', []), data.get('skins', [])
    parents = {}
    for index, node in enumerate(nodes):
        for child in node.get('children', []):
            if not 0 <= child < len(nodes) or child in parents:
                raise ValueError('Invalid node hierarchy')
            parents[child] = index
    for index in range(len(nodes)):
        visited = set()
        current = index
        while current in parents:
            if current in visited:
                raise ValueError('Cyclic node hierarchy')
            visited.add(current)
            current = parents[current]
    joint_nodes = set()
    skin_records = []
    for skin in skins:
        joints = skin.get('joints', [])
        if not joints or len(set(joints)) != len(joints) or any(not 0 <= j < len(nodes) for j in joints):
            raise ValueError('Invalid skin joints')
        joint_nodes.update(joints)
        inverse = skin.get('inverseBindMatrices')
        if inverse is not None and (not 0 <= inverse < len(accessors) or accessors[inverse]['type'] != 'MAT4' or accessors[inverse]['componentType'] != 5126 or accessors[inverse]['count'] != len(joints)):
            raise ValueError('Invalid inverse bind matrices')
        skin_records.append({'joints': len(joints), 'joint_names': [nodes[j].get('name', str(j)) for j in joints]})
    weighted_vertices = 0
    for node in nodes:
        if 'skin' not in node:
            continue
        if not 0 <= node['skin'] < len(skins) or 'mesh' not in node:
            raise ValueError('Invalid skinned node')
        joint_count = len(skins[node['skin']]['joints'])
        for primitive in data['meshes'][node['mesh']]['primitives']:
            attrs = primitive['attributes']
            if not all(key in attrs for key in ('JOINTS_0', 'WEIGHTS_0')):
                raise ValueError('Skinned mesh missing joint/weight attributes')
            j, w = attrs['JOINTS_0'], attrs['WEIGHTS_0']
            if accessors[j]['type'] != 'VEC4' or accessors[j]['componentType'] not in (5121, 5123) or accessors[w]['type'] != 'VEC4':
                raise ValueError('Invalid joint/weight representation')
            multiplier = {5121: 255, 5123: 65535}.get(accessors[w]['componentType'], 1)
            if multiplier != 1 and not accessors[w].get('normalized'):
                raise ValueError('Integer weights must be normalized')
            for joints, weights in zip(values[j], values[w], strict=True):
                weights = [x / multiplier for x in weights]
                if any(x < 0 or x > 1.001 for x in weights) or abs(sum(weights) - 1) > 0.002:
                    raise ValueError('Invalid skin weight sum')
                if any(joint >= joint_count for joint, weight in zip(joints, weights) if weight > 0):
                    raise ValueError('Skin joint index out of range')
                weighted_vertices += 1
    animations = []
    for animation in data.get('animations', []):
        samplers, dynamic = animation.get('samplers', []), 0
        duration = 0.0
        for channel in animation.get('channels', []):
            target = channel.get('target', {})
            sampler_id = channel.get('sampler', -1)
            if not 0 <= sampler_id < len(samplers) or not 0 <= target.get('node', -1) < len(nodes) or target.get('path') not in ('translation', 'rotation', 'scale'):
                raise ValueError('Unsupported/invalid animation channel')
            sampler = samplers[sampler_id]
            i, o = sampler.get('input', -1), sampler.get('output', -1)
            if not 0 <= i < len(accessors) or not 0 <= o < len(accessors):
                raise ValueError('Invalid animation sampler accessor')
            if accessors[i]['type'] != 'SCALAR' or accessors[i]['componentType'] != 5126:
                raise ValueError('Animation time must be float SCALAR')
            times = [row[0] for row in values[i]]
            if times[0] < 0 or any(b <= a for a, b in zip(times, times[1:])):
                raise ValueError('Animation time is not strictly increasing')
            interpolation = sampler.get('interpolation', 'LINEAR')
            factor = 3 if interpolation == 'CUBICSPLINE' else 1
            expected_type = 'VEC4' if target['path'] == 'rotation' else 'VEC3'
            if interpolation not in ('LINEAR', 'STEP', 'CUBICSPLINE') or accessors[o]['count'] != len(times) * factor or accessors[o]['type'] != expected_type:
                raise ValueError('Invalid animation interpolation/output')
            duration = max(duration, times[-1])
            if target['node'] in joint_nodes and any(max(row) != min(row) for row in zip(*values[o])):
                dynamic += 1
        animations.append({'name': animation.get('name', ''), 'duration': duration, 'channels': len(animation.get('channels', [])), 'dynamic_joint_channels': dynamic})
    return {'skins': skin_records, 'weighted_vertices': weighted_vertices, 'animations': animations}
