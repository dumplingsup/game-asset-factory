"""Real licensed rig+animations, local mesh edit, reusable motions and source rebuild."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from game_asset_factory.core import read, sha, write
from game_asset_factory.glb import validate_glb

root = Path(__file__).resolve().parents[1]
stamp = datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S')
output = root / 'artifacts/character_e2e' / stamp
output.mkdir(parents=True)
asset = 'fox-' + stamp
source = next((root / 'vendor/khronos-fox').glob('*/*.glb'))
commands = []
report = {'status': 'running', 'asset': asset, 'source_sha256': sha(source), 'commands': commands, 'visual_review': 'pending_human'}


def run(args, expected=0):
    command = [sys.executable, '-m', 'game_asset_factory.cli', '--root', str(root), *args]
    result = subprocess.run(command, capture_output=True, cwd=root, timeout=900)
    name = f'{len(commands)+1:02d}-' + args[0]
    (output / (name + '.stdout.log')).write_bytes(result.stdout)
    (output / (name + '.stderr.log')).write_bytes(result.stderr)
    commands.append({'argv': command, 'exit_code': result.returncode, 'expected': expected})
    write(output / 'e2e.json', report)
    print(name, result.returncode, flush=True)
    assert result.returncode == expected, result.stderr.decode(errors='replace')
    return json.loads(result.stdout if expected == 0 else result.stderr)


def build(revision):
    return run(['build', asset, '--plugin', 'blender-character', '--revision', revision])


def validate(built):
    return run(['validate', asset, '--build', built['build_id'], '--plugin', 'glb-character'])


try:
    original = validate_glb(source, allow_character=True)
    assert original['skins'][0]['joints'] == 24
    assert {a['name'] for a in original['animations']} == {'Run', 'Survey', 'Walk'}
    run(['ingest', asset, '--source', str(source), '--license-record', str(root / 'examples/fox.license.json'), '--recipe', str(root / 'examples/fox.recipe.json')])
    base = build('r0001')
    validate(base)
    base_preview = run(['preview', asset, '--build', base['build_id'], '--plugin', 'godot-character', '--material-mode', 'source', '--movie'])
    base_export = run(['export', asset, '--build', base['build_id']])
    edited = run(['edit', asset, '--build', base['build_id'], '--operation', str(root / 'examples/fox-left-ear.edit.json')])
    edit_report = read(Path(edited['path']) / 'edit_report.json')
    assert 0 < edit_report['vertices_modified'] < 0.1 * edit_report['total_vertices']
    assert edit_report['unselected_positions_unchanged'] and all(edit_report['preserved'].values())
    recipe = read(root / 'examples/fox.recipe.json')
    recipe.update(height_m=None, rotation_z_degrees=0)
    write(output / 'edited.recipe.json', recipe)
    run(['revise', asset, '--source', edited['editable_source'], '--recipe', str(output / 'edited.recipe.json'), '--note', 'Raise only the left ear tip: 15 source vertices, preserve rig/weights/UV/materials/actions'])
    variant = build('r0002')
    validate(variant)
    variant_preview = run(['preview', asset, '--build', variant['build_id'], '--plugin', 'godot-character', '--animation-source-build', base['build_id'], '--material-mode', 'source', '--movie'])
    variant_export = run(['export', asset, '--build', variant['build_id']])
    playback = read(Path(variant_preview['path']) / 'preview.json')
    assert playback['donor_sha256'] == base['model_sha256'] != variant['model_sha256']
    assert playback['animation_library_reloaded_from_disk'] and playback['motion_libraries']
    assert playback['bounds_method'] == 'baked_skinned_vertices_across_clips'
    assert playback['bones'] == 24 and {c['clip'] for c in playback['clips']} == {'Run', 'Walk', 'Survey'}
    assert all(c['bone_motion_radians'] > 0.01 and c['skinned_vertex_motion_m'] > 0.0001 and c['donor_pose_error_radians'] <= 0.002 for c in playback['clips'])
    rebuilt = build('r0002')
    validate(rebuilt)
    assert rebuilt['semantic_sha256'] == variant['semantic_sha256'], 'Edited-source rebuild changed output'
    run(['checkout', asset, '--revision', 'r0001'])
    rebuilt_base = build('r0001')
    validate(rebuilt_base)
    assert rebuilt_base['semantic_sha256'] == base['semantic_sha256'], 'Original-source regression changed output'
    # The original static importer must still refuse a real rig rather than stripping it.
    static_id = asset + '-static-reject'
    run(['ingest', static_id, '--source', str(source), '--license-record', str(root / 'examples/fox.license.json'), '--recipe', str(root / 'examples/lantern.recipe.json')])
    run(['build', static_id], expected=1)
    invalid = read(root / 'examples/fox-left-ear.edit.json')
    invalid['where']['bounds']['z'] = [100000, 200000]
    write(output / 'empty-region.json', invalid)
    run(['edit', asset, '--build', base['build_id'], '--operation', str(output / 'empty-region.json')], expected=1)
    report.update(status='passed', source_metrics=original, baseline=base, baseline_preview=base_preview, baseline_export=base_export,
                  edit=edited, edit_preserved=edit_report['preserved'], variant=variant, variant_preview=variant_preview, variant_export=variant_export,
                  playback=playback, edited_source_rebuild=rebuilt, original_source_rebuild=rebuilt_base,
                  edited_glb_byte_equal=rebuilt['model_sha256'] == variant['model_sha256'], original_glb_byte_equal=rebuilt_base['model_sha256'] == base['model_sha256'],
                  static_rig_rejected=True, empty_region_rejected=True)
except Exception as exc:
    report.update(status='failed', error=str(exc))
    raise
finally:
    write(output / 'e2e.json', report)
    print('Character E2E:', output / 'e2e.json', flush=True)
