"""Explicit GET of a pinned CC0 Morph regression fixture; never a KAI substitute."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '0f9a1b2fd99894736563d55b2c9dc9125700d081'
EXPECTED = 'b63f699f36d5db203a6029add68982148f4c3868f2ed1c9df0d404b5123a3d40'
directory = ROOT/'vendor/wolfman'/EXPECTED[:12]
directory.mkdir(parents=True,exist_ok=True)
files={}
for name,url in {
    'Wolfman.vrm':'https://arweave.net/wGhrzz7gMTxVeu8SeinAox3FO57BjQ09xjjcO4bOR9I',
    'avatars.json':f'https://raw.githubusercontent.com/ToxSam/open-source-avatars/{COMMIT}/data/avatars/100avatars-r1.json',
    'projects.json':f'https://raw.githubusercontent.com/ToxSam/open-source-avatars/{COMMIT}/data/projects.json',
    'CC0-1.0.txt':'https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt',
}.items():
    path=directory/name
    if path.is_file():
        payload=path.read_bytes()
    else:
        request=urllib.request.Request(url,headers={'User-Agent':'Game-Asset-Factory-local-review'})
        with urllib.request.urlopen(request,timeout=120) as response:
            payload=response.read()
    digest=hashlib.sha256(payload).hexdigest()
    if name=='Wolfman.vrm' and digest!=EXPECTED:
        raise ValueError('Wolfman content hash differs from the reviewed real fixture')
    if not path.exists():path.write_bytes(payload)
    files[name]={'url':url,'sha256':digest,'bytes':len(payload)}
(directory/'acquisition.json').write_text(json.dumps({'commit':COMMIT,'files':files,'purpose':'Morph format regression only; Wolfman has no original animation'},indent=2)+'\n',encoding='utf-8')
print(directory)
