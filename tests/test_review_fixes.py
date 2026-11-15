"""Fault injection tests registration transactions; E2E tests use real tools/assets."""
import shutil
from pathlib import Path

import pytest

from game_asset_factory.core import Factory, read, sha, source_files, write
from game_asset_factory.plugins import check_export_rights


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / 'model.glb'
    source.write_bytes(b'unit registration payload, not a model E2E')
    evidence = tmp_path / 'evidence.txt'
    evidence.write_text('unit evidence')
    license_path = tmp_path / 'rights.json'
    write(license_path, {'schema_version': 1, 'title': 'Contract', 'author': 'Test', 'source_url': 'https://example.invalid', 'source_version': '1', 'license': 'CC0-1.0', 'evidence': ['evidence.txt'], 'rights': {k: True for k in ('commercial_use', 'modification', 'runtime_distribution', 'source_distribution', 'third_party_upload')}})
    recipe = tmp_path / 'config.json'
    write(recipe, {'schema_version': 1, 'build_plugin': 'blender-static', 'blender_version': '5.2.3', 'objects': [], 'height_m': 2, 'subdivision_level': 0})
    return Factory(tmp_path / 'factory'), source, license_path, recipe


def test_ingest_copy_failure_is_retryable_with_log(inputs, monkeypatch):
    factory, source, license_path, recipe = inputs
    copy = shutil.copyfile

    def fail_during_snapshot(src, dst, **kwargs):
        if Path(dst).parent.name == 'licenses':
            raise OSError('injected disk copy failure')
        return copy(src, dst, **kwargs)

    monkeypatch.setattr(shutil, 'copyfile', fail_during_snapshot)
    with pytest.raises(OSError):
        factory.ingest('retry', source, license_path, recipe)
    assert not factory.path('retry').exists()
    failed = list((factory.root / 'artifacts/failed_transactions').glob('retry-ingest-*'))
    assert len(failed) == 1
    assert list((failed[0] / 'runs').glob('*/run.json'))
    assert read(next((failed[0] / 'runs').glob('*/run.json')))['status'] == 'failed'
    monkeypatch.setattr(shutil, 'copyfile', copy)
    factory.ingest('retry', source, license_path, recipe)
    factory.revision('retry')


def test_legacy_failed_ingest_directory_can_be_retried(inputs):
    factory, source, lic, recipe = inputs
    base = factory.path('legacy')
    write(base / 'runs/old-ingest/run.json', {'action': 'ingest', 'status': 'failed'})
    (base / 'partial.txt').write_text('retain me')
    factory.ingest('legacy', source, lic, recipe)
    factory.revision('legacy')
    archived = next((factory.root / 'artifacts/failed_transactions').glob('legacy-legacy-ingest-*'))
    assert (archived / 'partial.txt').read_text() == 'retain me'


@pytest.mark.parametrize('name', ['recipe.json', 'REVISION.JSON', 'asset.json', 'license.json', 'run.json'])
def test_metadata_names_rejected_before_creating_asset(inputs, name):
    factory, source, lic, recipe = inputs
    sidecar = source.parent / name
    sidecar.write_text('must not overwrite metadata')
    with pytest.raises(ValueError, match='metadata'):
        factory.ingest('collision', source, lic, recipe, [sidecar])
    assert not factory.path('collision').exists()


def test_revise_rejects_source_metadata_and_inherited_sidecar_collision(inputs):
    factory, source, lic, recipe = inputs
    side = source.parent / 'texture.png'
    side.write_bytes(b'unit sidecar')
    factory.ingest('sample', source, lic, recipe, [side])
    before = sha(factory.path('sample') / 'asset.json')
    with pytest.raises(ValueError, match='inherited sidecar'):
        factory.revise('sample', side, None, 'invalid rename')
    reserved = source.parent / 'revision.json'
    reserved.write_text('invalid')
    with pytest.raises(ValueError, match='metadata'):
        factory.revise('sample', reserved, None, 'invalid metadata')
    assert sha(factory.path('sample') / 'asset.json') == before
    side.write_bytes(b'explicit replacement')
    factory.revise('sample', source, None, 'replace texture intentionally', [side])
    assert (factory.path('sample') / 'source/r0002/texture.png').read_bytes() == b'explicit replacement'


def test_revise_copy_failure_does_not_block_same_revision(inputs, monkeypatch):
    factory, source, lic, recipe = inputs
    factory.ingest('sample', source, lic, recipe)
    before = sha(factory.path('sample') / 'asset.json')
    copy = shutil.copyfile
    monkeypatch.setattr(shutil, 'copyfile', lambda *_a, **_k: (_ for _ in ()).throw(OSError('disk failure')))
    with pytest.raises(OSError):
        factory.revise('sample', source, None, 'failed')
    assert sha(factory.path('sample') / 'asset.json') == before
    assert not (factory.path('sample') / 'source/r0002').exists()
    monkeypatch.setattr(shutil, 'copyfile', copy)
    assert factory.revise('sample', source, None, 'retry')['revision'] == 'r0002'


@pytest.mark.parametrize('commercial', [False, True])
@pytest.mark.parametrize('runtime', [False, True])
@pytest.mark.parametrize('usage', ['commercial', 'noncommercial'])
def test_commercial_use_is_independent_from_distribution(commercial, runtime, usage):
    rights = {'commercial_use': commercial, 'runtime_distribution': runtime}
    allowed = runtime and (commercial or usage == 'noncommercial')
    if allowed:
        check_export_rights(rights, usage)
    else:
        with pytest.raises(ValueError, match='rights denied'):
            check_export_rights(rights, usage)
