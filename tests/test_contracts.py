"""Fast contract tests. Real tools/model are tested separately by e2e.py."""
import json
from pathlib import Path

import pytest

from game_asset_factory.core import Factory, contained, read, sha, write
from game_asset_factory.glb import validate_glb
from game_asset_factory.plugins import LocalPlugin, require_local
from game_asset_factory.schemas import RECIPE, check


@pytest.fixture
def registered(tmp_path):
    source = tmp_path / 'input.blend'
    # Only tests registration storage, not model validity. Not an E2E substitute.
    source.write_bytes(b'registration contract payload')
    evidence = tmp_path / 'CC0.txt'
    evidence.write_text('Contract-test license evidence')
    license_path = tmp_path / 'license.json'
    write(license_path, {'schema_version': 1, 'title': 'Contract test', 'author': 'Test', 'source_url': 'https://example.invalid', 'source_version': '1', 'license': 'CC0-1.0', 'evidence': ['CC0.txt'], 'rights': {k: True for k in ('commercial_use', 'modification', 'runtime_distribution', 'source_distribution', 'third_party_upload')}})
    recipe = tmp_path / 'recipe.json'
    write(recipe, {'schema_version': 1, 'build_plugin': 'blender-static', 'blender_version': '5.2.3', 'objects': [], 'height_m': 2, 'subdivision_level': 0})
    factory = Factory(tmp_path / 'factory')
    factory.ingest('sample', source, license_path, recipe)
    return factory, source, license_path, recipe


def test_original_can_change_without_changing_ingested_snapshot(registered):
    factory, source, _, _ = registered
    before = sha(factory.path('sample') / 'raw/input.blend')
    source.write_bytes(b'changed external file')
    assert sha(factory.path('sample') / 'raw/input.blend') == before
    factory.revision('sample')


@pytest.mark.parametrize('relative', ['raw/input.blend', 'source/r0001/input.blend', 'licenses/00_CC0.txt'])
def test_tamper_is_rejected(registered, relative):
    factory, *_ = registered
    (factory.path('sample') / relative).write_bytes(b'tampered')
    with pytest.raises(ValueError, match='Integrity'):
        factory.revision('sample')


def test_revision_and_checkout_preserve_old_source(registered):
    factory, source, _, _ = registered
    original = sha(factory.path('sample') / 'source/r0001/input.blend')
    source.write_bytes(b'artist revision')
    assert factory.revise('sample', source, None, 'real user edit')['revision'] == 'r0002'
    factory.checkout('sample', 'r0001')
    assert factory.asset('sample')[1]['current_revision'] == 'r0001'
    assert sha(factory.path('sample') / 'source/r0001/input.blend') == original
    assert (factory.path('sample') / 'source/r0002/input.blend').read_bytes() == b'artist revision'


def test_duplicate_ingest_does_not_overwrite(registered):
    factory, source, license_path, recipe = registered
    old = sha(factory.path('sample') / 'asset.json')
    with pytest.raises(ValueError, match='already exists'):
        factory.ingest('sample', source, license_path, recipe)
    assert sha(factory.path('sample') / 'asset.json') == old


def test_path_escape_rejected(tmp_path):
    with pytest.raises(ValueError, match='escapes'):
        contained(tmp_path, '../outside')
    with pytest.raises(ValueError, match='ID'):
        Factory(tmp_path).path('../outside')


@pytest.mark.parametrize('capability', ['network', 'upload', 'paid'])
def test_remote_capabilities_denied(capability):
    plugin = LocalPlugin()
    setattr(plugin, capability, True)
    with pytest.raises(ValueError, match='rejects'):
        require_local(plugin)


def test_corrupt_glb_rejected(tmp_path):
    path = tmp_path / 'broken.glb'
    path.write_bytes(b'glTF' + b'\0' * 100)
    with pytest.raises(ValueError, match='header'):
        validate_glb(path)


def test_failed_operation_keeps_error_record(registered):
    factory, *_ = registered
    base = factory.path('sample')
    with pytest.raises(RuntimeError):
        with factory.run(base, 'failure-check'):
            raise RuntimeError('deliberate failure')
    reports = [read(p) for p in (base / 'runs').glob('*/run.json')]
    assert any(p['status'] == 'failed' and 'deliberate failure' in p['error'] for p in reports)


def test_recipe_envelope_is_not_blender_specific():
    check({'schema_version': 1, 'build_plugin': 'future-2d', 'settings': {'palette': 'limited'}}, RECIPE)
    with pytest.raises(ValueError):
        check({'schema_version': 1, 'build_plugin': 'blender-static'}, RECIPE)
