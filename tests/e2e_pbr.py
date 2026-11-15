"""Real multi-mesh/textured PBR sample and actual commercial policy rejection."""
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from game_asset_factory.core import read, write
from game_asset_factory.glb import validate_glb

root = Path(__file__).resolve().parents[1]
stamp = datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S')
output = root / 'artifacts/pbr_e2e' / stamp
output.mkdir(parents=True)
asset = 'lantern-' + stamp
source = next((root / 'vendor/khronos-lantern').glob('*/*.glb'))
commands = []
report = {'status': 'running', 'asset': asset, 'commands': commands, 'visual_review': 'pending_human'}


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


try:
    original = validate_glb(source)
    assert original['meshes'] >= 3 and original['embedded_images'] >= 4
    run(['ingest', asset, '--source', str(source), '--license-record', str(root / 'examples/lantern.license.json'), '--recipe', str(root / 'examples/lantern.recipe.json')])
    built = run(['build', asset])
    run(['validate', asset, '--build', built['build_id']])
    preview = run(['preview', asset, '--build', built['build_id'], '--material-mode', 'source', '--movie'])
    exported = run(['export', asset, '--build', built['build_id'], '--usage', 'commercial'])
    rebuilt = run(['build', asset])
    run(['validate', asset, '--build', rebuilt['build_id']])
    assert built['semantic_sha256'] == rebuilt['semantic_sha256']
    metrics = validate_glb(Path(exported['path']) / 'model.glb')
    assert metrics['meshes'] >= 3 and metrics['embedded_images'] >= 4
    assert metrics['material_channels'] == original['material_channels']
    godot = read(Path(preview['path']) / 'preview.json')
    assert godot['mesh_instances'] >= 3 and all(m['normal_texture'] and m['roughness_texture'] and m['albedo_texture'] for m in godot['materials'])
    # A real second asset/build with local noncommercial-only policy.
    lic = read(root / 'examples/lantern.license.json')
    lic['evidence'] = [str((root / 'examples' / p).resolve()) for p in lic['evidence']]
    lic['rights']['commercial_use'] = False
    lic['conditions'] += ' TEST ONLY: local factory usage is deliberately restricted; original CC0 is unaffected.'
    write(output / 'noncommercial.license.json', lic)
    nc = asset + '-nc'
    run(['ingest', nc, '--source', str(source), '--license-record', str(output / 'noncommercial.license.json'), '--recipe', str(root / 'examples/lantern.recipe.json')])
    nc_build = run(['build', nc])
    run(['validate', nc, '--build', nc_build['build_id']])
    run(['export', nc, '--build', nc_build['build_id'], '--usage', 'commercial'], 1)
    run(['export', nc, '--build', nc_build['build_id'], '--usage', 'noncommercial'])
    report.update(status='passed', source=str(source), source_metrics=original, output_metrics=metrics, build=built, preview=preview, export=exported, rebuild=rebuilt, commercial_denied_noncommercial_allowed=True)
except Exception as exc:
    report.update(status='failed', error=str(exc))
    raise
finally:
    write(output / 'e2e.json', report)
    print('PBR report:', output / 'e2e.json', flush=True)
