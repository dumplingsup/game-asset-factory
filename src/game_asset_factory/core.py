"""Engine-independent registration, revision and execution ledger."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

from . import __version__
from .schemas import check, LICENSE, RECIPE


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temp, path)


def safe_id(value):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', value):
        raise ValueError('ID must be 1-80 lowercase letters, digits, underscore or hyphen')
    return value


def contained(base, relative):
    target = (base / relative).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError('Path escapes asset directory')
    return target


def inventory(directory):
    return {p.relative_to(directory).as_posix(): sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def assert_inventory(base, hashes):
    for relative, expected in hashes.items():
        path = contained(base, relative)
        if not path.is_file() or sha(path) != expected:
            raise ValueError(f'Integrity mismatch: {relative}')


RESERVED_NAMES = {'asset.json', 'recipe.json', 'revision.json', 'license.json',
                  'build.json', 'run.json', 'export.json', 'validation.json'}


def source_files(source, sidecars=()):
    paths = [Path(source).resolve(), *(Path(p).resolve() for p in sidecars)]
    names = set()
    for path in paths:
        if not path.is_file():
            raise ValueError(f'Missing source/sidecar: {path}')
        name = path.name.casefold().rstrip(' .')
        if name in RESERVED_NAMES or name != path.name.casefold():
            raise ValueError(f'Source/sidecar filename conflicts with internal metadata: {path.name}')
        if name in names:
            raise ValueError(f'Source and sidecar names collide: {path.name}')
        names.add(name)
    return paths


def tool(name):
    variable = {'blender': 'BLENDER_BIN', 'godot': 'GODOT_BIN', 'ffmpeg': 'FFMPEG_BIN'}[name]
    value = os.environ.get(variable) or shutil.which(name)
    if not value or not Path(value).is_file():
        raise ValueError(f'{name} unavailable; set {variable}')
    return str(Path(value).resolve())


def process(command, log_dir, name, *, cwd=None, timeout=300):
    log_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    record = {'argv': list(map(str, command)), 'cwd': str(cwd or Path.cwd()), 'started_at': now()}
    # No shell, no credential/environment dump; kill the actual direct child on timeout.
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, creationflags=flags)
        stdout = result.stdout.decode('utf-8', errors='replace')
        stderr = result.stderr.decode('utf-8', errors='replace')
        record.update(exit_code=result.returncode, seconds=round(time.monotonic() - start, 4))
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b'').decode('utf-8', errors='replace')
        stderr = (exc.stderr or b'').decode('utf-8', errors='replace')
        record.update(exit_code=None, timed_out=True, seconds=round(time.monotonic() - start, 4))
        result = None
    (log_dir / (name + '.stdout.log')).write_text(stdout, encoding='utf-8')
    (log_dir / (name + '.stderr.log')).write_text(stderr, encoding='utf-8')
    write(log_dir / (name + '.process.json'), record)
    if result is None or result.returncode:
        raise RuntimeError(f'{name} failed; see {log_dir}')
    if re.search(r'(?m)^(?:ERROR|SCRIPT ERROR):', stdout + '\n' + stderr):
        raise RuntimeError(f'{name} engine error; see {log_dir}')
    return stdout.strip()


class Factory:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.assets = self.root / 'assets'

    def path(self, asset_id):
        return self.assets / safe_id(asset_id)

    def quarantine(self, directory, asset_id, action, error):
        """Move only checked factory-owned transaction paths; never delete evidence."""
        source = directory.resolve()
        failures = (self.root / 'artifacts/failed_transactions').resolve()
        target = failures / (safe_id(asset_id) + '-' + action + '-' + uuid.uuid4().hex)
        if source == self.assets.resolve() or not source.is_relative_to(self.assets.resolve()) or not target.resolve().is_relative_to(failures):
            raise ValueError('Transaction quarantine path escapes factory workspace')
        failures.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        write(target / 'transaction.json', {'asset': asset_id, 'action': action, 'status': 'failed',
              'original_path': str(directory), 'quarantined_at': now(), 'error': str(error)})
        return target

    def staging(self, asset_id, action):
        directory = self.assets / '.staging' / (safe_id(asset_id) + '-' + action + '-' + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        return directory

    @contextmanager
    def lock(self, asset_id):
        directory = self.assets / '.locks'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (safe_id(asset_id) + '.lock')
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            raise ValueError(f'Asset locked: {path}; inspect previous process before removing stale lock') from None
        try:
            os.write(fd, f'{os.getpid()} {now()}'.encode())
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def asset(self, asset_id):
        base = self.path(asset_id)
        data = read(base / 'asset.json')
        if data.get('id') != asset_id or data.get('schema_version') != 1:
            raise ValueError('Invalid asset identity/schema')
        assert_inventory(base, data['protected_files'])
        return base, data

    def revision(self, asset_id, revision=None):
        base, asset = self.asset(asset_id)
        revision = safe_id(revision or asset['current_revision'])
        directory = base / 'source' / revision
        revision_data = read(directory / 'revision.json')
        if sha(directory / 'revision.json') != asset['revisions'][revision]:
            raise ValueError('Revision manifest changed')
        assert_inventory(directory, revision_data['files'])
        check(read(directory / 'recipe.json'), RECIPE)
        return base, asset, directory, revision_data

    @contextmanager
    def run(self, base, action, *, plugin=None, inputs=None):
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S') + '-' + action + '-' + uuid.uuid4().hex[:8]
        directory = base / 'runs' / run_id
        directory.mkdir(parents=True)
        package = Path(__file__).parent
        code = {p.relative_to(package).as_posix(): sha(p) for p in sorted(package.rglob('*')) if p.is_file() and p.suffix in ('.py', '.gd', '.godot')}
        data = {'schema_version': 1, 'id': run_id, 'action': action, 'started_at': now(),
                'status': 'running', 'factory_version': __version__, 'code_hashes': code,
                'plugin': plugin, 'inputs': inputs or {}, 'visual_review': 'pending_human'}
        write(directory / 'run.json', data)
        try:
            yield directory, data
            data['status'] = 'succeeded'
        except Exception as exc:
            data.update(status='failed', error=f'{type(exc).__name__}: {exc}')
            raise
        finally:
            data['ended_at'] = now()
            write(directory / 'run.json', data)

    def ingest(self, asset_id, source, license_path, recipe_path, sidecars=()):
        source, license_path = Path(source).resolve(), Path(license_path).resolve()
        license_data, recipe = read(license_path), read(recipe_path)
        check(license_data, LICENSE)
        check(recipe, RECIPE)
        sources = source_files(source, sidecars)
        input_hashes = {path.name: sha(path) for path in sources}
        expected = license_data.get('expected_source_sha256')
        if expected and input_hashes[source.name] != expected:
            raise ValueError('Source hash differs from license record')
        evidence = [Path(p) if Path(p).is_absolute() else license_path.parent / p for p in license_data['evidence']]
        if any(not p.is_file() for p in evidence):
            raise ValueError('License evidence missing')
        base = self.path(asset_id)
        if base.exists():
            runs = [read(p) for p in (base / 'runs').glob('*/run.json')]
            legacy_failed = not (base / 'asset.json').exists() and runs and all(r.get('action') == 'ingest' and r.get('status') == 'failed' for r in runs)
            if not legacy_failed:
                raise ValueError('Asset already exists; use revise (unrecognized existing directories are preserved)')
            self.quarantine(base, asset_id, 'legacy-ingest', 'Retry of failed 0.1 ingest')
        stage = self.staging(asset_id, 'ingest')
        try:
            with self.run(stage, 'ingest', inputs={'source_sha256': input_hashes[source.name], 'file_hashes': input_hashes, 'license_record_sha256': sha(license_path)}) as (run_dir, record):
                (stage / 'raw').mkdir()
                for path in sources:
                    shutil.copyfile(path, stage / 'raw' / path.name)
                assert_inventory(stage / 'raw', input_hashes)
                lic_dir = stage / 'licenses'
                lic_dir.mkdir()
                copied = []
                for index, path in enumerate(evidence):
                    name = f'{index:02d}_' + path.name
                    shutil.copyfile(path, lic_dir / name)
                    copied.append(name)
                license_data['evidence'] = copied
                write(lic_dir / 'license.json', license_data)
                directory = stage / 'source/r0001'
                shutil.copytree(stage / 'raw', directory)
                write(directory / 'recipe.json', recipe)
                revision = {'schema_version': 1, 'id': 'r0001', 'source': source.name, 'created_at': now(), 'note': 'Initial licensed ingest', 'files': inventory(directory)}
                write(directory / 'revision.json', revision)
                protected = {**{'raw/' + k: v for k, v in inventory(stage / 'raw').items()}, **{'licenses/' + k: v for k, v in inventory(lic_dir).items()}}
                asset = {'schema_version': 1, 'id': asset_id, 'created_at': now(), 'current_revision': 'r0001', 'protected_files': protected, 'revisions': {'r0001': sha(directory / 'revision.json')}, 'visual_review': 'pending_human'}
                write(stage / 'asset.json', asset)
                record['outputs'] = {'asset': 'asset.json', 'revision': 'r0001', 'protected_files': protected}
            stage.rename(base)
        except Exception as exc:
            if stage.exists():
                # Publication can fail after the run context completed.
                for path in (stage / 'runs').glob('*/run.json'):
                    data = read(path)
                    data.update(status='failed', error=str(exc))
                    write(path, data)
                self.quarantine(stage, asset_id, 'ingest', exc)
            raise
        return asset

    def revise(self, asset_id, source, recipe_path, note, sidecars=()):
        base, asset, old_dir, old_revision = self.revision(asset_id)
        source = Path(source).resolve()
        explicit = source_files(source, sidecars)
        inherited = {relative: old_dir / relative for relative in old_revision['files'] if relative not in (old_revision['source'], 'recipe.json')}
        if any(Path(relative).name.casefold() == source.name.casefold() for relative in inherited):
            raise ValueError('New source name collides with inherited sidecar; rename the source explicitly')
        replacements = {p.name.casefold(): p for p in explicit[1:]}
        inherited = {name: path for name, path in inherited.items() if Path(name).name.casefold() not in replacements}
        files = source_files(source, [*inherited.values(), *explicit[1:]])
        recipe = read(recipe_path) if recipe_path else read(old_dir / 'recipe.json')
        check(recipe, RECIPE)
        if not read(base / 'licenses/license.json')['rights']['modification']:
            raise ValueError('Modification rights denied')
        new_id = f'r{max(int(r[1:]) for r in asset["revisions"]) + 1:04d}'
        directory = base / 'source' / new_id
        if directory.exists():
            raise ValueError('Unregistered revision directory already exists; preserve and inspect it')
        stage = self.staging(asset_id, 'revise')
        published = committed = False
        try:
            with self.run(base, 'revise', inputs={'parent': old_revision['id'], 'source_sha256': sha(source), 'note': note, 'explicit_sidecars': [p.name for p in explicit[1:]]}) as (_, record):
                for path in files:
                    shutil.copyfile(path, stage / path.name)
                write(stage / 'recipe.json', recipe)
                revision = {'schema_version': 1, 'id': new_id, 'source': source.name, 'parent': old_revision['id'], 'created_at': now(), 'note': note, 'files': inventory(stage)}
                write(stage / 'revision.json', revision)
                stage.rename(directory)
                published = True
                asset['revisions'][new_id] = sha(directory / 'revision.json')
                asset['current_revision'] = new_id
                write(base / 'asset.json', asset)
                committed = True
                record['outputs'] = {'revision': new_id, 'revision_sha256': asset['revisions'][new_id]}
        except Exception as exc:
            if not committed:
                self.quarantine(directory if published else stage, asset_id, 'revise', exc)
            raise
        return {'revision': new_id}

    def checkout(self, asset_id, revision):
        base, asset, _, _ = self.revision(asset_id, revision)
        with self.run(base, 'checkout', inputs={'previous': asset['current_revision'], 'target': revision}):
            asset['current_revision'] = revision
            write(base / 'asset.json', asset)
        return {'current_revision': revision}

    def build_record(self, base, build_id):
        directory = base / 'builds' / safe_id(build_id)
        run = read(base / 'runs' / build_id / 'run.json')
        if run.get('status') != 'succeeded' or run.get('action') != 'build' or sha(directory / 'build.json') != run['outputs']['build_manifest_sha256']:
            raise ValueError('Build receipt missing or changed')
        data = read(directory / 'build.json')
        if data['status'] != 'succeeded':
            raise ValueError('Build not successful')
        assert_inventory(directory, data['outputs'])
        return directory, data

    def execute(self, action, asset_id, plugin, *, revision=None, build_id=None, movie=False, material_mode='clay', usage='commercial', operation=None, animation_source_build=None, profile=None, preview_config=None):
        from .plugins import Context, require_local
        require_local(plugin)
        base, asset, rev_dir, rev = self.revision(asset_id, revision)
        if action == 'build' and read(rev_dir / 'recipe.json')['build_plugin'] != plugin.name:
            raise ValueError('Build plugin differs from pinned source recipe')
        inputs = {'revision': rev['id'], 'revision_sha256': asset['revisions'][rev['id']], 'license_sha256': sha(base / 'licenses/license.json')}
        if action != 'build':
            build_dir, build = self.build_record(base, build_id)
            if revision is not None and revision != build['revision']:
                raise ValueError('Requested revision differs from build revision')
            base, asset, rev_dir, rev = self.revision(asset_id, build['revision'])
            inputs.update(revision=rev['id'], revision_sha256=asset['revisions'][rev['id']])
            inputs.update(build=build_id, artifact_hashes=build['outputs'])
        else:
            build_dir, build = None, None
        with self.run(base, action, plugin=plugin.name, inputs=inputs) as (run_dir, record):
            if operation is not None:
                record['inputs']['operation'] = operation
            if preview_config is not None:
                record['inputs']['preview_config'] = preview_config
            context = Context(self, base, rev_dir, rev, run_dir, record, build_dir, build, movie, material_mode, usage, operation, animation_source_build, profile, preview_config)
            result = plugin.run(context)
            record['outputs'] = result
        return result
