import argparse
import json
from pathlib import Path
import sys

from .core import Factory, process, read, tool
from .plugins import registry


def main():
    parser = argparse.ArgumentParser(prog='gaf', description='Local Game Asset Factory; technical results never approve visual quality')
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Factory repository/data root')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    commands.add_parser('plugins')
    ingest = commands.add_parser('ingest')
    ingest.add_argument('asset')
    ingest.add_argument('--source', required=True, type=Path)
    ingest.add_argument('--license-record', required=True, type=Path)
    ingest.add_argument('--recipe', required=True, type=Path)
    ingest.add_argument('--sidecar', action='append', default=[], type=Path)
    revise = commands.add_parser('revise')
    revise.add_argument('asset')
    revise.add_argument('--source', required=True, type=Path)
    revise.add_argument('--recipe', type=Path)
    revise.add_argument('--note', required=True)
    revise.add_argument('--sidecar', action='append', default=[], type=Path)
    checkout = commands.add_parser('checkout')
    checkout.add_argument('asset')
    checkout.add_argument('--revision', required=True)
    status = commands.add_parser('status')
    status.add_argument('asset')
    defaults = {'build': 'blender-static', 'validate': 'glb-static', 'preview': 'godot-generic', 'export': 'glb', 'edit': 'blender-character-edit'}
    for action, default in defaults.items():
        command = commands.add_parser(action)
        command.add_argument('asset')
        command.add_argument('--plugin', default=default)
        command.add_argument('--revision')
        if action != 'build':
            command.add_argument('--build', required=True)
        if action == 'preview':
            command.add_argument('--movie', action='store_true')
            command.add_argument('--material-mode', choices=['clay', 'source'], default='clay')
            command.add_argument('--animation-source-build', help='Reuse animation library from another validated build of this asset')
        if action == 'export':
            command.add_argument('--usage', choices=['commercial', 'noncommercial'], default='commercial')
            command.add_argument('--profile', help='Export profile; automatically selected for character builds')
        if action == 'edit':
            command.add_argument('--operation', required=True, type=Path)
    args = parser.parse_args()
    factory = Factory(args.root)
    try:
        if args.command == 'doctor':
            report = {}
            log_dir = factory.root / 'artifacts/doctor'
            for name in ('blender', 'godot', 'ffmpeg'):
                report[name] = {'path': tool(name), 'version': process([tool(name), '-version' if name == 'ffmpeg' else '--version'], log_dir, name).splitlines()[0]}
            result = report
        elif args.command == 'plugins':
            result = [{'name': p.name, 'action': p.action, 'category': p.category, 'network': p.network, 'upload': p.upload, 'paid': p.paid} for p in registry().values()]
        else:
            with factory.lock(args.asset):
                if args.command == 'ingest':
                    result = factory.ingest(args.asset, args.source, args.license_record, args.recipe, args.sidecar)
                elif args.command == 'revise':
                    result = factory.revise(args.asset, args.source, args.recipe, args.note, args.sidecar)
                elif args.command == 'checkout':
                    result = factory.checkout(args.asset, args.revision)
                elif args.command == 'status':
                    _, result = factory.asset(args.asset)
                else:
                    plugins = registry()
                    plugin = plugins.get(args.plugin)
                    if plugin is None or plugin.action != args.command:
                        raise ValueError('No implemented plugin for this command: ' + args.plugin)
                    result = factory.execute(args.command, args.asset, plugin, revision=args.revision, build_id=getattr(args, 'build', None), movie=getattr(args, 'movie', False), material_mode=getattr(args, 'material_mode', 'clay'), usage=getattr(args, 'usage', 'commercial'), operation=read(args.operation) if getattr(args, 'operation', None) else None, animation_source_build=getattr(args, 'animation_source_build', None), profile=getattr(args, 'profile', None))
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
