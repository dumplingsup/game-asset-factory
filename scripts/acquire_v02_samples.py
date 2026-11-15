"""Explicit download of two reviewed public samples, never uploads local assets."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--commit', default='8f492390ddc7a2ae221a1369ef560589cf8c70fb')
args = parser.parse_args()


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Game-Asset-Factory-local-review'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


commit = args.commit
base = 'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/' + commit
for name in ('Lantern', 'Fox'):
    directory = ROOT / 'vendor' / ('khronos-' + name.lower()) / commit[:12]
    directory.mkdir(parents=True, exist_ok=True)
    urls = {'README.md': f'{base}/Models/{name}/README.md', name + '.glb': f'{base}/Models/{name}/glTF-Binary/{name}.glb'}
    urls['CC0-1.0.txt'] = 'https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt'
    if name == 'Fox':
        urls['CC-BY-4.0.txt'] = 'https://creativecommons.org/licenses/by/4.0/legalcode.txt'
    files = {}
    for filename, url in urls.items():
        path = directory / filename
        payload = path.read_bytes() if path.exists() else fetch(url)
        if not path.exists():
            path.write_bytes(payload)
        files[filename] = {'url': url, 'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}
    record = {'repository': 'KhronosGroup/glTF-Sample-Assets', 'commit': commit, 'model': name, 'files': files}
    (directory / 'acquisition.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'model': name, 'directory': str(directory), 'commit': commit, 'bytes': files[name + '.glb']['bytes']}), flush=True)
