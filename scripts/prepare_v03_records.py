"""Explicitly record reviewed official KAI/Kenney ZIPs and primary license evidence.

Obtain both archives normally first. Only public metadata/legal texts are fetched;
no asset upload, login handling, purchase or paid API is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

from game_asset_factory.core import read,sha,write

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-zip',type=Path,required=True)
parser.add_argument('--equipment-zip',type=Path,required=True)
args=parser.parse_args()
kai_sha='fc4d52913e4151fb62622f084ea8093c30c1bf09bdf2d4d0fb69f936cd05dd5d'
gear_sha='19c4648680cb1d2e8836cade96cbf9781c0c1f45fbc6d2ce41cee8239a3ec4d8'
if sha(args.source_zip)!=kai_sha or sha(args.equipment_zip)!=gear_sha:
    raise ValueError('Unreviewed archive versions: inspect rights/content before adding another profile')
directory=ROOT/'vendor/kai'/kai_sha[:12]
directory.mkdir(parents=True,exist_ok=True)
files={}
for name,url in {
    'kai-metadata.json':'https://api.sketchfab.com/v3/models/aa56e447b578470b8d6b1b9587fd29ac',
    'CC-BY-4.0.txt':'https://creativecommons.org/licenses/by/4.0/legalcode.txt',
}.items():
    path=directory/name
    if not path.exists():
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Game-Asset-Factory-local-review'}),timeout=60) as response:
            payload=response.read()
        path.write_bytes(payload)
    files[name]={'url':url,'sha256':sha(path)}
metadata=read(directory/'kai-metadata.json')
if metadata['license']['slug']!='by' or metadata['user']['displayName']!='Realidad Aumentada Empezando Desde Cero':
    raise ValueError('Official KAI license/identity differs; re-review before integration')
with zipfile.ZipFile(args.equipment_zip) as stream:
    gear_license=stream.read('License.txt')
if b'Creative Commons CC0' not in gear_license and b'CC0' not in gear_license:
    raise ValueError('Kenney source license evidence differs')
(directory/'Kenney-License.txt').write_bytes(gear_license)
write(directory/'acquisition.json',{'kai_zip_sha256':kai_sha,'kenney_zip_sha256':gear_sha,'files':files,'uploads':False,'fees':0})
record={'schema_version':1,'title':'KAI - The Little Fox Warrior (Animated)',
    'author':metadata['user']['displayName'],'source_url':metadata['viewerUrl'],'source_version':metadata['updatedAt']+'; official ZIP '+kai_sha,
    'license':'CC-BY-4.0','expected_source_sha256':'bc7b919637f182f8128d921030c050cb4aab6d34299cabe34fc9658120e0259d',
    'evidence':['kai-metadata.json','CC-BY-4.0.txt','acquisition.json'],
    'rights':{'commercial_use':True,'modification':True,'runtime_distribution':True,'source_distribution':True,'third_party_upload':False},
    'conditions':'Credit Realidad Aumentada Empezando Desde Cero, link https://creativecommons.org/licenses/by/4.0/, mark modifications; no endorsement implied.'}
write(directory/'kai.license.json',record)
print(directory/'kai.license.json')
