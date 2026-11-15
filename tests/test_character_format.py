"""Corrupt copies of the real licensed Fox; never generate a fake rig fixture."""
import json
from pathlib import Path
import struct

import pytest

from game_asset_factory.glb import validate_glb
from game_asset_factory.schemas import CHARACTER_RECIPE, check


@pytest.fixture
def real_fox():
    root = Path(__file__).resolve().parents[1]
    files = list((root / 'vendor/khronos-fox').glob('*/*.glb'))
    assert files, 'Acquire the pinned real Fox sample before running character format tests'
    return files[0]


def rewrite(source, destination, change):
    raw = source.read_bytes()
    json_size = struct.unpack_from('<I', raw, 12)[0]
    data = json.loads(raw[20:20 + json_size])
    binary = bytearray(raw[28 + json_size:])
    change(data, binary)
    encoded = json.dumps(data, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    payload = struct.pack('<II', len(encoded), 0x4e4f534a) + encoded + struct.pack('<II', len(binary), 0x004e4942) + binary
    destination.write_bytes(struct.pack('<4sII', b'glTF', 2, len(payload) + 12) + payload)


def test_real_character_has_all_three_dynamic_joint_clips(real_fox):
    data = validate_glb(real_fox, allow_character=True)
    assert data['skins'][0]['joints'] == 24 and data['weighted_vertices'] > 1000
    assert {a['name'] for a in data['animations']} == {'Run', 'Walk', 'Survey'}
    assert all(a['dynamic_joint_channels'] > 0 for a in data['animations'])
    with pytest.raises(ValueError, match='Static profile'):
        validate_glb(real_fox)


def test_bad_joint_reference_rejected(real_fox, tmp_path):
    invalid = tmp_path / 'bad.glb'
    rewrite(real_fox, invalid, lambda data, _: data['skins'][0]['joints'].__setitem__(0, len(data['nodes']) + 1))
    with pytest.raises(ValueError, match='skin joints'):
        validate_glb(invalid, allow_character=True)


def test_bad_animation_sampler_rejected(real_fox, tmp_path):
    invalid = tmp_path / 'bad.glb'
    rewrite(real_fox, invalid, lambda data, _: data['animations'][0]['channels'][0].__setitem__('sampler', 100000))
    with pytest.raises(ValueError, match='animation channel'):
        validate_glb(invalid, allow_character=True)


def test_bad_weights_rejected(real_fox, tmp_path):
    invalid = tmp_path / 'bad.glb'

    def change(data, binary):
        accessor = data['accessors'][data['meshes'][0]['primitives'][0]['attributes']['WEIGHTS_0']]
        assert accessor['componentType'] == 5126
        view = data['bufferViews'][accessor['bufferView']]
        offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
        struct.pack_into('<f', binary, offset, 2.0)

    rewrite(real_fox, invalid, change)
    with pytest.raises(ValueError, match='weight sum'):
        validate_glb(invalid, allow_character=True)


def test_character_recipe_refuses_unpinned_or_missing_settings():
    with pytest.raises(ValueError):
        check({'schema_version': 1, 'build_plugin': 'blender-character'}, CHARACTER_RECIPE)
