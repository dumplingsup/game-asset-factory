"""Format negatives on copies of real CC0 Wolfman, plus real geometry correspondence.

The added weight sampler is a format-unit fixture only. Animated character E2E
uses the actual KAI clips and Blender-authored facial action, not this sampler.
"""
import copy
import hashlib
import json
from pathlib import Path
import struct

import pytest

from game_asset_factory.glb import validate_glb
from game_asset_factory.resources.character_integrity import compare_morph_geometry
from game_asset_factory.schemas import CHARACTER_PREVIEW, CHARACTER_RECIPE, check


@pytest.fixture
def real_morph():
    files=list((Path(__file__).resolve().parents[1]/'vendor/wolfman').glob('*/Wolfman.vrm'))
    assert files,'Run scripts/acquire_v03_samples.py first'
    assert hashlib.sha256(files[0].read_bytes()).hexdigest()=='b63f699f36d5db203a6029add68982148f4c3868f2ed1c9df0d404b5123a3d40'
    return files[0]


def document(source):
    raw=source.read_bytes();size=struct.unpack_from('<I',raw,12)[0]
    return json.loads(raw[20:20+size]),bytearray(raw[28+size:])


def save(path,data,binary):
    data['buffers'][0]['byteLength']=len(binary)
    binary+=b'\0'*(-len(binary)%4)
    encoded=json.dumps(data,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4)
    body=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    path.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
    return path


def append(data,binary,payload):
    binary+=b'\0'*(-len(binary)%4)
    index=len(data['bufferViews'])
    data['bufferViews'].append({'buffer':0,'byteOffset':len(binary),'byteLength':len(payload)})
    binary+=payload
    return index


def dense_values(data,binary,index):
    accessor=data['accessors'][index];view=data['bufferViews'][accessor['bufferView']]
    width={'VEC3':3,'SCALAR':1}[accessor['type']]
    return [struct.unpack_from('<'+'f'*width,binary,view.get('byteOffset',0)+accessor.get('byteOffset',0)+i*view.get('byteStride',width*4)) for i in range(accessor['count'])]


def test_real_morph_counts_and_opt_in(real_morph):
    actual=validate_glb(real_morph,allow_character=True,allow_morph=True)
    assert actual['skins'][0]['joints']==65 and not actual['animations']
    assert actual['morph_target_count']==16
    assert sum(any(p['nonzero_position_vertices'] for p in t) for t in actual['morph_meshes'][0]['targets'])==15
    with pytest.raises(ValueError,match='morph targets'):
        validate_glb(real_morph,allow_character=True)
    with pytest.raises(ValueError,match='character profile'):
        validate_glb(real_morph,allow_morph=True)


@pytest.mark.parametrize('failure',['target_count','target_type','target_index','names','node_weights'])
def test_malformed_real_morph_rejected(real_morph,tmp_path,failure):
    data,binary=document(real_morph);primitive=data['meshes'][0]['primitives'][0]
    if failure=='target_count':data['accessors'][primitive['targets'][0]['POSITION']]['count']-=1
    elif failure=='target_type':primitive['targets'][0]['COLOR_0']=primitive['targets'][0].pop('POSITION')
    elif failure=='target_index':primitive['targets'][0]['POSITION']=999999
    elif failure=='names':data['meshes'][0]['extras']={'targetNames':['duplicate']*16}
    else:next(n for n in data['nodes'] if 'mesh' in n)['weights']=[0]
    with pytest.raises(ValueError,match='[Mm]orph'):
        validate_glb(save(tmp_path/'bad.glb',data,binary),allow_character=True,allow_morph=True)


@pytest.mark.parametrize('failure',[None,'duplicate','out_of_range','count','value_range'])
def test_sparse_real_morph_preserves_deltas_or_rejects_corruption(real_morph,tmp_path,failure):
    expected=validate_glb(real_morph,allow_character=True,allow_morph=True)['morph_meshes']
    data,binary=document(real_morph)
    index=data['meshes'][0]['primitives'][0]['targets'][0]['POSITION']
    rows=dense_values(data,binary,index);selected=[i for i,row in enumerate(rows) if any(x!=0 for x in row)]
    indices=selected.copy()
    if failure=='duplicate':indices[1]=indices[0]
    if failure=='out_of_range':indices[-1]=len(rows)
    iv=append(data,binary,struct.pack('<'+'I'*len(indices),*indices))
    vv=append(data,binary,b''.join(struct.pack('<fff',*rows[i]) for i in selected))
    accessor=data['accessors'][index];accessor.pop('bufferView');accessor.pop('byteOffset',None)
    accessor['sparse']={'count':len(selected),'indices':{'bufferView':iv,'componentType':5125},'values':{'bufferView':vv}}
    if failure=='count':accessor['sparse']['count']=len(rows)+1
    if failure=='value_range':data['bufferViews'][vv]['byteLength']-=12
    path=save(tmp_path/'sparse.glb',data,binary)
    if failure:
        with pytest.raises(ValueError,match='[Ss]parse'):validate_glb(path,allow_character=True,allow_morph=True)
    else:
        assert validate_glb(path,allow_character=True,allow_morph=True)['morph_meshes']==expected


@pytest.mark.parametrize('bad_count',[False,True])
def test_weights_animation_on_real_mesh(real_morph,tmp_path,bad_count):
    data,binary=document(real_morph)
    tv=append(data,binary,struct.pack('<ff',0,1))
    ov=append(data,binary,struct.pack('<'+'f'*32,*([0]*16+[1]+[0]*15)))
    time_id=len(data['accessors'])
    data['accessors'] += [{'bufferView':tv,'componentType':5126,'type':'SCALAR','count':2},
                          {'bufferView':ov,'componentType':5126,'type':'SCALAR','count':31 if bad_count else 32}]
    node=next(i for i,n in enumerate(data['nodes']) if 'mesh' in n)
    data['animations']=[{'name':'format-unit-weight-channel','samplers':[{'input':time_id,'output':time_id+1}],
        'channels':[{'sampler':0,'target':{'node':node,'path':'weights'}}]}]
    path=save(tmp_path/'weights.glb',data,binary)
    if bad_count:
        with pytest.raises(ValueError,match='animation interpolation/output'):validate_glb(path,allow_character=True,allow_morph=True)
    else:
        assert validate_glb(path,allow_character=True,allow_morph=True)['animations'][0]['dynamic_morph_channels']==1


def test_same_bone_names_with_changed_bind_are_not_compatible(real_morph,tmp_path):
    before=validate_glb(real_morph,allow_character=True,allow_morph=True)
    data,binary=document(real_morph)
    node=data['nodes'][data['skins'][0]['joints'][1]]
    node['translation'][1]+=0.1
    after=validate_glb(save(tmp_path/'changed-rest.glb',data,binary),allow_character=True,allow_morph=True)
    assert before['skins']==after['skins']
    assert before['skeleton_signature_sha256']!=after['skeleton_signature_sha256']


def test_correspondence_uses_real_deltas_and_tolerates_seam_splits(real_morph):
    data,binary=document(real_morph);p=data['meshes'][0]['primitives'][0]
    positions=dense_values(data,binary,p['attributes']['POSITION'])
    delta=dense_values(data,binary,p['targets'][0]['POSITION'])
    reference={'real-mesh':{'names':['actual-face-key'],'positions':positions,'deltas':[delta]}}
    split=copy.deepcopy(reference)
    split['real-mesh']['positions']+=positions[:5];split['real-mesh']['deltas'][0]+=delta[:5]
    compare_morph_geometry(reference,split)
    split['real-mesh']['deltas'][0][50]=(10,0,0)
    with pytest.raises(RuntimeError,match='correspondence|difference|delta|geometry'):
        compare_morph_geometry(reference,split)


def test_morph_recipe_and_preview_config_are_explicit():
    recipe={'schema_version':1,'build_plugin':'blender-character','blender_version':'5.2.3','height_m':None,'rotation_z_degrees':0,'animation_fps':60,'morph_targets':'preserve','static_pose_actions':['T-Pose']}
    check(recipe,CHARACTER_RECIPE)
    with pytest.raises(ValueError):check({**recipe,'morph_targets':'discard'},CHARACTER_RECIPE)
    with pytest.raises(ValueError):check({'schema_version':1,'mode':'performance','sample_frames':1},CHARACTER_PREVIEW)
    with pytest.raises(ValueError):check({'schema_version':1,'mode':'interactive','upload':True},CHARACTER_PREVIEW)
