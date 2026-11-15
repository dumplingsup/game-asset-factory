"""Create records for the two reviewed, pinned samples already downloaded locally."""
from pathlib import Path
from game_asset_factory.core import read, sha, write

root = Path(__file__).resolve().parents[1]
for name in ('Lantern', 'Fox'):
    directory = next((root / 'vendor' / ('khronos-' + name.lower())).iterdir())
    acquisition = read(directory / 'acquisition.json')
    authors = 'Microsoft / sbtron; Frank Galligan (compression)' if name == 'Lantern' else 'PixelMannen (model); tomkranis (rig and animation); AsoboStudio and scurest (glTF conversion)'
    evidence = [directory / 'README.md', directory / 'CC0-1.0.txt', directory / 'acquisition.json']
    if name == 'Fox':
        evidence.append(directory / 'CC-BY-4.0.txt')
    notice = directory / 'ATTRIBUTION.txt'
    notice.write_text(f'{name}\nAuthors: {authors}\nSource: https://github.com/KhronosGroup/glTF-Sample-Assets/tree/{acquisition["commit"]}/Models/{name}\nLicense: ' + ('CC0-1.0' if name == 'Lantern' else 'Model CC0-1.0; rigging/animation and glTF conversion CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/)') + '\nFactory derivatives may normalize transforms, modify a local region, re-export, and reuse the original motions. See the source revision recipe and build reports for exact changes. No endorsement is claimed. Original notices and license text retained.\n', encoding='utf-8', newline='\n')
    evidence.append(notice)
    record = {'schema_version': 1, 'title': name, 'author': authors,
              'source_url': f'https://github.com/KhronosGroup/glTF-Sample-Assets/tree/{acquisition["commit"]}/Models/{name}',
              'source_version': acquisition['commit'], 'license': 'CC0-1.0' if name == 'Lantern' else 'CC0-1.0 AND CC-BY-4.0',
              'evidence': [p.relative_to(root / 'examples').as_posix() if p.is_relative_to(root / 'examples') else '../' + p.relative_to(root).as_posix() for p in evidence],
              'expected_source_sha256': sha(directory / (name + '.glb')),
              'rights': {'commercial_use': True, 'modification': True, 'runtime_distribution': True, 'source_distribution': True, 'third_party_upload': False},
              'attribution_required': name == 'Fox', 'conditions': 'Retain attribution, license links and notices, mark modifications. Factory upload policy remains disabled.'}
    write(root / 'examples' / (name.lower() + '.license.json'), record)
write(root / 'examples/lantern.recipe.json', {'schema_version': 1, 'build_plugin': 'blender-static', 'blender_version': '5.2.3', 'objects': [], 'height_m': 1.5, 'subdivision_level': 0})
