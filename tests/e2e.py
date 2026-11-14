"""Real local tools + real licensed model. Retains every command and failure log."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from game_asset_factory.core import read, sha, write
from game_asset_factory.glb import validate_glb

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--asset', default='cc0-human')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
output = root / 'artifacts/e2e' / stamp
output.mkdir(parents=True)
report = {'started_at': datetime.now(timezone.utc).isoformat(), 'asset': args.asset, 'commands': [], 'status': 'running', 'visual_review': 'pending_human'}
counter = 0


def run(arguments, expected=0):
    global counter
    counter += 1
    name = f'{counter:02d}-' + arguments[0]
    command = [sys.executable, '-m', 'game_asset_factory.cli', '--root', str(root), *arguments]
    start = time.monotonic()
    result = subprocess.run(command, cwd=root, capture_output=True, timeout=900,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    stdout, stderr = result.stdout.decode('utf-8', errors='replace'), result.stderr.decode('utf-8', errors='replace')
    (output / (name + '.stdout.log')).write_text(stdout, encoding='utf-8')
    (output / (name + '.stderr.log')).write_text(stderr, encoding='utf-8')
    record = {'argv': command, 'exit_code': result.returncode, 'expected': expected,
              'seconds': round(time.monotonic() - start, 3), 'stdout': name + '.stdout.log', 'stderr': name + '.stderr.log'}
    report['commands'].append(record)
    write(output / 'e2e.json', report)
    print(f'{name}: exit={result.returncode} expected={expected}', flush=True)
    if result.returncode != expected:
        raise RuntimeError(f'Unexpected exit for {name}; {stderr[-1500:]}')
    return json.loads(stdout if expected == 0 else stderr)


try:
    source = args.source.resolve()
    license_file = root / 'examples/cc0-human.license.json'
    recipe = root / 'examples/cc0-human.recipe.json'
    report['source_sha256'] = sha(source)
    run(['ingest', args.asset, '--source', str(source), '--license-record', str(license_file), '--recipe', str(recipe)])
    first = run(['build', args.asset])
    run(['validate', args.asset, '--build', first['build_id']])
    preview = run(['preview', args.asset, '--build', first['build_id'], '--movie'])
    exported = run(['export', args.asset, '--build', first['build_id']])
    second = run(['build', args.asset, '--revision', 'r0001'])
    run(['validate', args.asset, '--build', second['build_id']])
    second_export = run(['export', args.asset, '--build', second['build_id']])
    assert first['build_id'] != second['build_id']
    assert first['semantic_sha256'] == second['semantic_sha256'], 'Source rebuild semantic mismatch'
    assert sha(Path(exported['path']) / 'model.glb') == first['model_sha256']
    assert sha(Path(second_export['path']) / 'model.glb') == second['model_sha256']
    report['rebuild'] = {'first': first['build_id'], 'second': second['build_id'], 'semantic_equal': True,
                         'glb_byte_equal': first['model_sha256'] == second['model_sha256'], 'semantic_sha256': first['semantic_sha256']}
    # Save an editable-source revision and roll the active source back; old builds remain.
    revised_recipe = read(recipe)
    revised_recipe['objects'] = []
    revised_recipe['rotation_z_degrees'] = 0
    write(output / 'editable.recipe.json', revised_recipe)
    revision = run(['revise', args.asset, '--source', str(Path(first['path']) / 'editable.blend'), '--recipe', str(output / 'editable.recipe.json'), '--note', 'E2E snapshot of real processed editable source'])
    assert revision['revision'] == 'r0002'
    editable_build = run(['build', args.asset, '--revision', 'r0002'])
    run(['validate', args.asset, '--build', editable_build['build_id']])
    first_metrics = validate_glb(Path(first['path']) / 'model.glb')
    editable_metrics = validate_glb(Path(editable_build['path']) / 'model.glb')
    assert first_metrics['geometry_sha256_at_1e_5'] == editable_metrics['geometry_sha256_at_1e_5'], 'Editable .blend geometry roundtrip mismatch'
    report['editable_source_roundtrip'] = {'revision': 'r0002', 'build_id': editable_build['build_id'], 'geometry_equal_at_1e_5_m': True}
    run(['checkout', args.asset, '--revision', 'r0001'])
    assert run(['status', args.asset])['current_revision'] == 'r0001'
    # Deliberately corrupt the real GLB in a test, log the mutation, and restore exact bytes.
    model = Path(first['path']) / 'model.glb'
    original = model.read_bytes()
    write(output / 'negative-tamper.json', {'file': str(model), 'before_sha256': sha(model), 'operation': 'replace GLB magic for format and post-validation integrity rejection; restore in finally'})
    try:
        model.write_bytes(b'BAD!' + original[4:])
        try:
            validate_glb(model)
        except ValueError as exc:
            report['corrupt_actual_glb_rejected'] = str(exc)
        else:
            raise AssertionError('Corrupt actual GLB accepted')
        run(['export', args.asset, '--build', first['build_id']], expected=1)
    finally:
        model.write_bytes(original)
    assert sha(model) == first['model_sha256']
    report['tampered_build_rejected_and_restored'] = True
    denied = read(license_file)
    denied['evidence'] = [str(root / 'examples' / p) for p in denied['evidence']]
    denied['rights']['runtime_distribution'] = False
    write(output / 'no-distribution.license.json', denied)
    restricted_id = args.asset + '-restricted'
    run(['ingest', restricted_id, '--source', str(source), '--license-record', str(output / 'no-distribution.license.json'), '--recipe', str(recipe)])
    restricted = run(['build', restricted_id])
    run(['validate', restricted_id, '--build', restricted['build_id']])
    run(['export', restricted_id, '--build', restricted['build_id']], expected=1)
    report.update(status='passed', first_build=first, preview=preview, export=exported, restricted_export_rejected=True)
except Exception as exc:
    report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    raise
finally:
    report['ended_at'] = datetime.now(timezone.utc).isoformat()
    write(output / 'e2e.json', report)
    print('E2E report:', output / 'e2e.json', flush=True)
