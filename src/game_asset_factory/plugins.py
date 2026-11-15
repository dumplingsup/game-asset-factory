"""Entry-point plugins; only implemented local capabilities are registered."""
from dataclasses import dataclass, replace
from importlib.metadata import entry_points
from pathlib import Path
import shutil

from .core import assert_inventory, inventory, process, read, safe_id, sha, tool, write
from .glb import validate_glb

RESOURCES = Path(__file__).parent / 'resources'


@dataclass
class Context:
    factory: object
    asset: Path
    revision_dir: Path
    revision: dict
    run_dir: Path
    run_record: dict
    build_dir: Path | None
    build: dict | None
    movie: bool
    material_mode: str = 'clay'
    usage: str = 'commercial'
    operation: dict | None = None
    animation_source_build: str | None = None
    profile: str | None = None

    def output(self, kind):
        directory = self.asset / kind / self.run_dir.name
        directory.mkdir(parents=True)
        return directory


def require_local(plugin):
    if plugin.network or plugin.upload or plugin.paid:
        raise ValueError('Base factory rejects network/upload/paid plugins; no upload authorization is implied')


class LocalPlugin:
    network = upload = paid = False


def check_export_rights(rights, usage, required=()):
    if usage not in ('commercial', 'noncommercial'):
        raise ValueError('Export usage must be commercial or noncommercial')
    requirements = set(required) | {'runtime_distribution'}
    if usage == 'commercial':
        requirements.add('commercial_use')
    denied = sorted(right for right in requirements if not rights.get(right, False))
    if denied:
        raise ValueError('Export rights denied for ' + usage + ': ' + ', '.join(denied))


def blender(ctx, action, output):
    request = {'action': action, 'output': str(output), 'source': str(ctx.revision_dir / ctx.revision['source']),
               'recipe': read(ctx.revision_dir / 'recipe.json'),
               'model': str(ctx.build_dir / 'model.glb') if ctx.build_dir else None}
    request_path = ctx.run_dir / 'blender_request.json'
    write(request_path, request)
    command = [tool('blender'), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '23', '--python', str(RESOURCES / 'blender_worker.py'), '--', str(request_path)]
    process(command, ctx.run_dir, 'blender-' + action, timeout=600)
    report = read(output / 'blender_report.json')
    if report['version'] != request['recipe']['blender_version']:
        raise ValueError(f'Blender version mismatch: {report["version"]}')
    return report


class BlenderStatic(LocalPlugin):
    name, action, category = 'blender-static', 'build', '3d'

    def run(self, ctx):
        if not read(ctx.asset / 'licenses/license.json')['rights']['modification']:
            raise ValueError('Modification rights denied')
        output = ctx.output('builds')
        report = blender(ctx, 'build', output)
        metrics = validate_glb(output / 'model.glb')
        write(output / 'format_metrics.json', metrics)
        data = {'schema_version': 1, 'id': ctx.run_dir.name, 'status': 'succeeded', 'revision': ctx.revision['id'],
                'revision_sha256': sha(ctx.revision_dir / 'revision.json'), 'recipe_sha256': sha(ctx.revision_dir / 'recipe.json'),
                'tool_version': report['version'], 'outputs': inventory(output), 'visual_review': 'pending_human'}
        write(output / 'build.json', data)
        return {'build_id': ctx.run_dir.name, 'build_manifest_sha256': sha(output / 'build.json'), 'path': str(output), 'model_sha256': sha(output / 'model.glb'), 'semantic_sha256': metrics['semantic_sha256']}


class GlbValidate(LocalPlugin):
    name, action, category = 'glb-static', 'validate', '3d'

    def run(self, ctx):
        metrics = validate_glb(ctx.build_dir / 'model.glb')
        imported = blender(ctx, 'inspect', ctx.run_dir)
        if imported['triangles_evaluated'] != metrics['triangles_mesh_definitions'] or imported['mesh_objects'] < 1:
            raise ValueError('Blender reimport geometry does not match GLB')
        report = {'technical_status': 'passed', 'build_id': ctx.build['id'], 'model_sha256': sha(ctx.build_dir / 'model.glb'),
                  'format': metrics, 'blender_reimport': imported, 'visual_review': 'pending_human'}
        write(ctx.run_dir / 'validation.json', report)
        return {'validation_id': ctx.run_dir.name, 'report_sha256': sha(ctx.run_dir / 'validation.json'), 'technical_status': 'passed'}


def receipt(ctx, required_plugin='glb-static'):
    for run in sorted((ctx.asset / 'runs').glob('*/run.json'), reverse=True):
        data = read(run)
        if data.get('action') != 'validate' or data.get('plugin') != required_plugin or data.get('status') != 'succeeded' or data.get('inputs', {}).get('build') != ctx.build['id']:
            continue
        report = run.parent / 'validation.json'
        if not report.is_file() or sha(report) != data['outputs']['report_sha256']:
            raise ValueError('Validation receipt changed')
        report_data = read(report)
        if report_data['technical_status'] == 'passed' and report_data['model_sha256'] == sha(ctx.build_dir / 'model.glb'):
            return data['id']
    raise ValueError('Run validate on this exact build before preview/export')


class GodotPreview(LocalPlugin):
    name, action, category = 'godot-generic', 'preview', 'preview'

    def run(self, ctx):
        validation = receipt(ctx)
        output = ctx.output('previews')
        viewer = output / 'viewer'
        shutil.copytree(RESOURCES / 'godot', viewer)
        version = process([tool('godot'), '--version'], ctx.run_dir, 'godot-version')
        if not version.startswith('4.7.2.'):
            raise ValueError('Base preview is verified with Godot 4.7.2; different version requires explicit adapter validation')
        command = [tool('godot'), '--path', str(viewer), '--script', str(viewer / 'preview.gd'), '--disable-vsync']
        if ctx.movie:
            command += ['--write-movie', str(output / 'turntable.avi'), '--fixed-fps', '30']
        command += ['--', '--model=' + str(ctx.build_dir / 'model.glb'), '--output=' + str(output), '--material-mode=' + ctx.material_mode]
        process(command, ctx.run_dir, 'godot-preview', timeout=180)
        report = read(output / 'preview.json')
        if report['mesh_instances'] < 1 or len(report['captures']) != 4:
            raise ValueError('Godot preview missing meshes/captures')
        for capture in report['captures']:
            path = output / capture['file']
            if not path.is_file() or path.stat().st_size < 1024:
                raise ValueError('Missing/empty rendered image')
        if ctx.movie:
            process([tool('ffmpeg'), '-hide_banner', '-loglevel', 'warning', '-y', '-i', str(output / 'turntable.avi'), '-an', '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output / 'turntable.mp4')], ctx.run_dir, 'ffmpeg', timeout=180)
        report.update(model_sha256=sha(ctx.build_dir / 'model.glb'), validation_id=validation, godot_version=version, visual_review='pending_human')
        write(output / 'preview.json', report)
        return {'preview_id': ctx.run_dir.name, 'path': str(output), 'files': inventory(output), 'visual_review': 'pending_human'}


class GlbExport(LocalPlugin):
    name, action, category = 'glb', 'export', 'export'

    def run(self, ctx):
        license_data = read(ctx.asset / 'licenses/license.json')
        profile_id = safe_id(ctx.profile or ('glb-character' if ctx.build.get('kind') == 'character' else 'glb'))
        profile_path = ctx.factory.root / 'profiles' / (profile_id + '.json')
        profile = read(profile_path)
        if profile.get('id') != profile_id or profile.get('plugin') != self.name or profile.get('includes_source') is not False:
            raise ValueError('Unsupported GLB profile contract')
        validation = receipt(ctx, profile['requires_validation'])
        check_export_rights(license_data['rights'], ctx.usage, profile['requires_rights'])
        output = ctx.output('exports')
        shutil.copyfile(ctx.build_dir / 'model.glb', output / 'model.glb')
        shutil.copytree(ctx.asset / 'licenses', output / 'notices')
        write(output / 'export.json', {'schema_version': 1, 'id': ctx.run_dir.name, 'profile': profile_id, 'asset': ctx.asset.name,
              'source_revision': ctx.build['revision'], 'source_revision_sha256': ctx.build['revision_sha256'], 'build_id': ctx.build['id'],
              'build_manifest_sha256': sha(ctx.build_dir / 'build.json'), 'model_sha256': sha(output / 'model.glb'),
              'validation_id': validation, 'profile_sha256': sha(profile_path), 'rights': license_data['rights'], 'license': license_data['license'],
              'usage': ctx.usage, 'source_files_included': False, 'visual_review': 'pending_human'})
        return {'export_id': ctx.run_dir.name, 'path': str(output), 'files': inventory(output), 'visual_review': 'pending_human'}


def character_blender(ctx, action, output):
    if not read(ctx.asset / 'licenses/license.json')['rights']['modification']:
        raise ValueError('Modification rights denied')
    model = None
    if ctx.build_dir is not None:
        model = ctx.build_dir / ('editable.blend' if action == 'edit' else 'model.glb')
    request = {'action': action, 'output': str(output), 'source': str(ctx.revision_dir / ctx.revision['source']),
               'model': str(model) if model else None, 'recipe': read(ctx.revision_dir / 'recipe.json'), 'operation': ctx.operation}
    path = ctx.run_dir / 'character_request.json'
    write(path, request)
    process([tool('blender'), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '23', '--python', str(RESOURCES / 'character_worker.py'), '--', str(path)], ctx.run_dir, 'blender-character-' + action, timeout=600)
    return read(output / 'blender_report.json')


class BlenderCharacter(LocalPlugin):
    name, action, category = 'blender-character', 'build', 'animation'

    def run(self, ctx):
        output = ctx.output('builds')
        report = character_blender(ctx, 'build', output)
        source = read(output / 'input_snapshot.json')
        metrics = validate_glb(output / 'model.glb', allow_character=True)
        names = {clip['name'] for clip in metrics['animations']}
        if not metrics['skins'] or not metrics['weighted_vertices'] or names != {clip['name'] for clip in source['actions']}:
            raise ValueError('Export lost skin or animation clips')
        for clip in metrics['animations']:
            action = next(a for a in source['actions'] if a['name'] == clip['name'])
            fps = read(ctx.revision_dir / 'recipe.json')['animation_fps']
            expected = (action['frame_range'][1] - action['frame_range'][0]) / fps
            if clip['dynamic_joint_channels'] < 1 or abs(clip['duration'] - expected) > 1 / fps + 0.001:
                raise ValueError('Exported clip lost bone motion or timing')
        if {name for skin in metrics['skins'] for name in skin['joint_names']} != set(source['bone_names']):
            raise ValueError('Export changed joint names')
        for key in ('bones_sha256', 'weights_sha256', 'uv_sha256', 'actions_sha256', 'materials_sha256', 'images_sha256'):
            if report[key] != source[key]:
                raise ValueError('Build changed protected character data: ' + key)
        write(output / 'format_metrics.json', metrics)
        data = {'schema_version': 1, 'id': ctx.run_dir.name, 'kind': 'character', 'status': 'succeeded', 'revision': ctx.revision['id'],
                'revision_sha256': sha(ctx.revision_dir / 'revision.json'), 'recipe_sha256': sha(ctx.revision_dir / 'recipe.json'),
                'tool_version': report['version'], 'outputs': inventory(output), 'visual_review': 'pending_human'}
        write(output / 'build.json', data)
        return {'build_id': ctx.run_dir.name, 'build_manifest_sha256': sha(output / 'build.json'), 'path': str(output),
                'model_sha256': sha(output / 'model.glb'), 'semantic_sha256': metrics['semantic_sha256'], 'animations': sorted(names)}


class GlbCharacterValidate(LocalPlugin):
    name, action, category = 'glb-character', 'validate', 'animation'

    def run(self, ctx):
        if ctx.build.get('kind') != 'character':
            raise ValueError('Character validator requires character build')
        metrics = validate_glb(ctx.build_dir / 'model.glb', allow_character=True)
        imported = character_blender(ctx, 'inspect', ctx.run_dir)
        if imported['skinned_meshes'] < 1 or imported['bones'] != sum(s['joints'] for s in metrics['skins']) or imported['triangles_evaluated'] != metrics['triangles_mesh_definitions']:
            raise ValueError('Reimport lost geometry/skin/bones')
        if {a['name'] for a in imported['actions']} != {a['name'] for a in metrics['animations']}:
            raise ValueError('Reimport lost animation actions')
        write(ctx.run_dir / 'validation.json', {'technical_status': 'passed', 'build_id': ctx.build['id'], 'model_sha256': sha(ctx.build_dir / 'model.glb'),
              'format': metrics, 'blender_reimport': imported, 'visual_review': 'pending_human'})
        return {'validation_id': ctx.run_dir.name, 'report_sha256': sha(ctx.run_dir / 'validation.json'), 'technical_status': 'passed'}


class CharacterEdit(LocalPlugin):
    name, action, category = 'blender-character-edit', 'edit', 'animation'

    def run(self, ctx):
        receipt(ctx, 'glb-character')
        if not ctx.operation:
            raise ValueError('An explicit local edit operation is required')
        output = ctx.output('edits')
        character_blender(ctx, 'edit', output)
        report = read(output / 'edit_report.json')
        return {'edit_id': ctx.run_dir.name, 'path': str(output), 'editable_source': str(output / 'editable.blend'),
                'vertices_modified': report['vertices_modified'], 'files': inventory(output), 'visual_review': 'pending_human'}


class GodotCharacterPreview(LocalPlugin):
    name, action, category = 'godot-character', 'preview', 'animation'

    def run(self, ctx):
        validation = receipt(ctx, 'glb-character')
        donor_dir, donor_build = (ctx.build_dir, ctx.build)
        if ctx.animation_source_build:
            donor_dir, donor_build = ctx.factory.build_record(ctx.asset, ctx.animation_source_build)
            receipt(replace(ctx, build_dir=donor_dir, build=donor_build), 'glb-character')
        ctx.run_record['inputs']['animation_donor'] = {'build_id': donor_build['id'], 'model_sha256': sha(donor_dir / 'model.glb')}
        output = ctx.output('previews')
        viewer = output / 'viewer'
        shutil.copytree(RESOURCES / 'godot', viewer)
        version = process([tool('godot'), '--version'], ctx.run_dir, 'godot-version')
        if not version.startswith('4.7.2.'):
            raise ValueError('Character preview requires verified Godot 4.7.2')
        command = [tool('godot'), '--path', str(viewer), '--script', str(viewer / 'character_preview.gd'), '--disable-vsync']
        if ctx.movie:
            command += ['--write-movie', str(output / 'animation.avi'), '--fixed-fps', '30']
        command += ['--', '--model=' + str(ctx.build_dir / 'model.glb'), '--donor=' + str(donor_dir / 'model.glb'), '--output=' + str(output), '--material-mode=' + ctx.material_mode]
        process(command, ctx.run_dir, 'godot-character-preview', timeout=240)
        report = read(output / 'preview.json')
        if not report['animation_library_reused'] or not report['animation_library_reloaded_from_disk'] or report['bones'] < 1 or report['skinned_meshes'] < 1 or not report['clips']:
            raise ValueError('Missing actual character animation proof')
        expected_clips = {a['name'] for a in read(ctx.build_dir / 'format_metrics.json')['animations']}
        if {c['clip'] for c in report['clips']} != expected_clips:
            raise ValueError('Godot did not preview every exported clip')
        for shot in report['captures']:
            if (output / shot['file']).stat().st_size < 1024:
                raise ValueError('Empty animation capture')
        if ctx.movie:
            process([tool('ffmpeg'), '-hide_banner', '-loglevel', 'warning', '-y', '-i', str(output / 'animation.avi'), '-an', '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output / 'animation.mp4')], ctx.run_dir, 'ffmpeg-animation', timeout=180)
        report.update(validation_id=validation, godot_version=version, model_sha256=sha(ctx.build_dir / 'model.glb'), donor_sha256=sha(donor_dir / 'model.glb'), visual_review='pending_human')
        write(output / 'preview.json', report)
        return {'preview_id': ctx.run_dir.name, 'path': str(output), 'files': inventory(output), 'visual_review': 'pending_human'}


def registry():
    plugins = {p.name: p for p in (BlenderStatic(), GlbValidate(), GodotPreview(), GlbExport(), BlenderCharacter(), GlbCharacterValidate(), CharacterEdit(), GodotCharacterPreview())}
    for entry in entry_points(group='game_asset_factory.plugins'):
        plugin = entry.load()()
        if plugin.name in plugins:
            raise ValueError('Duplicate plugin: ' + plugin.name)
        for attribute in ('name', 'action', 'category', 'network', 'upload', 'paid', 'run'):
            if not hasattr(plugin, attribute):
                raise ValueError('Invalid plugin contract: ' + entry.name)
        plugins[plugin.name] = plugin
    return plugins
