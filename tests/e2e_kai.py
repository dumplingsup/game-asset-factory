"""Real KAI + Kenney authoring/reuse/rebuild through the existing factory.

Supply the official ZIPs and reviewed KAI license record. No network, login,
upload or generated replacement model. All commands and failed logs are retained.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from game_asset_factory.core import read, sha, write, process, tool
from game_asset_factory.glb import validate_glb

ROOT = Path(__file__).resolve().parents[1]
KAI_ZIP = 'fc4d52913e4151fb62622f084ea8093c30c1bf09bdf2d4d0fb69f936cd05dd5d'
KAI_GLB = 'bc7b919637f182f8128d921030c050cb4aab6d34299cabe34fc9658120e0259d'
KENNEY_ZIP = '19c4648680cb1d2e8836cade96cbf9781c0c1f45fbc6d2ce41cee8239a3ec4d8'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-zip', required=True, type=Path)
    parser.add_argument('--equipment-zip', required=True, type=Path)
    parser.add_argument('--kai-license-record', required=True, type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S')
    out = ROOT / 'artifacts/kai_e2e' / stamp
    out.mkdir(parents=True)
    asset, original_asset = 'kai-' + stamp, 'kai-original-' + stamp
    report = {'status':'running','asset':asset,'original_asset':original_asset,'commands':[],
              'visual_review':'pending_human','fees':{'api':0,'assets':0},'started_at':datetime.now(timezone.utc).isoformat()}
    start = time.monotonic()

    def run(arguments, expected=0):
        command = [sys.executable,'-m','game_asset_factory.cli','--root',str(ROOT),*map(str,arguments)]
        label = f'{len(report["commands"])+1:02d}-' + arguments[0]
        then = time.monotonic()
        result = subprocess.run(command,cwd=ROOT,capture_output=True,timeout=900)
        (out/(label+'.stdout.log')).write_bytes(result.stdout)
        (out/(label+'.stderr.log')).write_bytes(result.stderr)
        report['commands'].append({'argv':command,'exit_code':result.returncode,'expected':expected,'seconds':round(time.monotonic()-then,3)})
        write(out/'e2e.json',report)
        print(label,result.returncode,flush=True)
        assert result.returncode==expected,result.stderr.decode(errors='replace')
        return json.loads(result.stdout if expected==0 else result.stderr)

    def build(identity,revision):
        return run(['build',identity,'--revision',revision,'--plugin','blender-character'])

    def validate(identity,built):
        return run(['validate',identity,'--build',built['build_id'],'--plugin','glb-character'])

    def preview(built,config,movie=False,donor=None):
        arguments=['preview',asset,'--build',built['build_id'],'--plugin','godot-character','--material-mode','source',
                   '--config',ROOT/'examples'/config]
        if movie: arguments+=['--movie']
        if donor: arguments+=['--animation-source-build',donor['build_id']]
        return run(arguments)

    def extract(archive,directory):
        directory.mkdir()
        with zipfile.ZipFile(archive) as stream:
            for item in stream.infolist():
                target=(directory/item.filename).resolve()
                if not target.is_relative_to(directory.resolve()) or item.filename.startswith(('/', '\\')):
                    raise ValueError('Archive path escapes extraction directory')
            stream.extractall(directory)

    try:
        assert sha(args.source_zip)==KAI_ZIP,'Unreviewed KAI ZIP version'
        assert sha(args.equipment_zip)==KENNEY_ZIP,'Unreviewed Kenney ZIP version'
        # Exact archives are preserved as ingest sidecars, not just selected meshes.
        kai_archive=out/'kai_original.zip';shutil.copyfile(args.source_zip,kai_archive)
        gear_archive=out/'kenney_mini_dungeon.zip';shutil.copyfile(args.equipment_zip,gear_archive)
        extract(kai_archive,out/'kai-unpacked');extract(gear_archive,out/'kenney-unpacked')
        source=out/'kai-unpacked/source/Warrior Fox.glb'
        assert sha(source)==KAI_GLB
        original_metrics=validate_glb(source,allow_character=True)
        assert len(original_metrics['animations'])==8 and original_metrics['meshes']==1 and original_metrics['materials']==1
        record=read(args.kai_license_record)
        # Resolve evidence exactly as ingest would relative to the supplied record.
        record['evidence']=[str((args.kai_license_record.resolve().parent/p).resolve()) for p in record['evidence']]
        record['expected_source_sha256']=KAI_GLB
        write(out/'kai.license.json',record)
        run(['ingest',original_asset,'--source',source,'--license-record',out/'kai.license.json','--recipe',ROOT/'examples/kai.recipe.json','--sidecar',kai_archive])
        original=build(original_asset,'r0001');validate(original_asset,original)
        authored=out/'authoring'
        process([tool('blender'),'--background','--factory-startup','--disable-autoexec','--python-exit-code','23',
            '--python',str(ROOT/'scripts/prepare_kai_sample.py'),'--','--source',str(Path(original['path'])/'editable.blend'),
            '--equipment-dir',str(out/'kenney-unpacked/Models/GLB format'),'--plan',str(ROOT/'examples/kai-authoring.json'),
            '--output',str(authored)],out,'blender-authoring',timeout=600)
        authoring=read(authored/'authoring_report.json')
        assert all(authoring['preserved'].values()) and len(authoring['added_shapes'])==2 and len(authoring['added_equipment'])==3
        assert len(authoring['original_clips'])==8 and authoring['added_clips']==['Face_Expressions']
        # The combined derivative carries both sources and explicit modification notices.
        derivative={**record,'title':'KAI outfitted derivative with authored facial morphs',
            'author':record['author']+'; Kenney (equipment); local scripted authoring (facial keys, expression clip and equipment fit)',
            'license':'CC-BY-4.0 AND CC0-1.0','source_version':record['source_version']+'; Kenney Mini Dungeon 2.0 ZIP '+KENNEY_ZIP,
            'expected_source_sha256':sha(authored/'kai_prepared.blend'),
            'conditions':record.get('conditions','')+' Added: Kenney sword, spear and shield; two local facial shape keys and one expression clip; canonical orientation. Original KAI had no morphs or separate equipment. Original 8 action curves, rest rig, skin weights and UV retained.',
            'evidence':record['evidence']+[str(out/'kenney-unpacked/License.txt'),str(authored/'authoring_report.json'),str(ROOT/'examples/kai-authoring.json')]}
        write(out/'derived.license.json',derivative)
        run(['ingest',asset,'--source',authored/'kai_prepared.blend','--license-record',out/'derived.license.json',
             '--recipe',ROOT/'examples/kai-edited.recipe.json','--sidecar',kai_archive,'--sidecar',gear_archive,'--sidecar',authored/'authoring_report.json'])
        base=build(asset,'r0001');validate(asset,base)
        metrics=read(Path(base['path'])/'format_metrics.json')
        assert metrics['meshes']==4 and metrics['materials']==2 and metrics['morph_target_count']==2 and metrics['skins'][0]['joints']==41
        source_durations={c['name']:c['duration'] for c in original_metrics['animations']}
        for clip in metrics['animations']:
            if clip['name'] in source_durations: assert abs(clip['duration']-source_durations[clip['name']])<0.001
        inspection=preview(base,'kai-preview.json',True)
        movement=preview(base,'kai-third-person.json',True)
        performance=preview(base,'kai-performance.json')
        export=run(['export',asset,'--build',base['build_id']])
        edited=run(['edit',asset,'--build',base['build_id'],'--operation',ROOT/'examples/kai-ear.edit.json'])
        edit_report=read(Path(edited['path'])/'edit_report.json')
        assert 0<edit_report['vertices_modified']<edit_report['total_vertices']*0.1
        assert all(edit_report['preserved'].values()) and edit_report['unselected_positions_unchanged']
        run(['revise',asset,'--source',edited['editable_source'],'--recipe',ROOT/'examples/kai-edited.recipe.json',
             '--note','Smooth bounded right ear tip raise; preserve face keys, rig, weights, original and added clips, UV and materials'])
        variant=build(asset,'r0002');validate(asset,variant)
        variant_inspection=preview(variant,'kai-preview.json',True,base)
        variant_movement=preview(variant,'kai-third-person.json',True,base)
        variant_performance=preview(variant,'kai-performance.json',donor=base)
        variant_export=run(['export',asset,'--build',variant['build_id']])
        notices=read(Path(variant_export['path'])/'notices/modifications.json')
        assert 'ear tip' in notices['changes'][-1]['note'] and notices['changes'][-1]['revision']=='r0002'
        playback=read(Path(variant_inspection['path'])/'preview.json')
        assert playback['donor_sha256']==base['model_sha256']!=variant['model_sha256']
        assert len(playback['clips'])==9 and len(playback['morph_checks'])==2 and not playback['cross_skeleton_retargeting']
        expected_face={k['name']:k['max_world_delta_m'] for k in authoring['added_shapes']}
        for preview_result in (inspection,variant_inspection):
            actual=read(Path(preview_result['path'])/'preview.json')
            for shape in actual['morph_checks']:
                assert abs(shape['max_world_delta_m']-expected_face[shape['morph']])<0.0001,'Godot world-space face deformation differs from authored source'
            assert next(c for c in actual['clips'] if c['clip']=='Face_Expressions')['morph_vertex_motion_m']>0.02
            assert all(c['donor_morph_weight_error']<=0.0001 for c in actual['clips'])
        before_views={s['view']:s['camera'] for s in read(Path(inspection['path'])/'preview.json')['captures'] if s.get('view') in ('front','back','left')}
        after_views={s['view']:s['camera'] for s in playback['captures'] if s.get('view') in ('front','back','left')}
        assert before_views==after_views and len(before_views)==3,'Before/after comparison camera changed'
        rebuilt=build(asset,'r0002');validate(asset,rebuilt)
        assert rebuilt['semantic_sha256']==variant['semantic_sha256'],'Edited source rebuild differs'
        run(['checkout',asset,'--revision','r0001'])
        rolled_back=build(asset,'r0001');validate(asset,rolled_back)
        assert rolled_back['semantic_sha256']==base['semantic_sha256'],'Rollback rebuild differs'
        # Guardrails run against the real validated build, never a replacement rig.
        bad=read(ROOT/'examples/kai-third-person.json');bad['equipment_sets']=[{'name':'conflict','active':['Sword','Spear']}]
        write(out/'bad-slot.json',bad)
        conflict=run(['preview',asset,'--build',base['build_id'],'--plugin','godot-character','--config',out/'bad-slot.json'],1)
        assert 'one slot' in conflict['error']
        movie_perf=run(['preview',asset,'--build',base['build_id'],'--plugin','godot-character','--config',ROOT/'examples/kai-performance.json','--movie'],1)
        assert 'fixed-FPS' in movie_perf['error']
        report.update(status='passed',original=original,original_metrics=original_metrics,authoring=authoring,
            baseline=base,inspection=inspection,movement=movement,performance=performance,export=export,
            edit=edited,edit_preserved=edit_report['preserved'],variant=variant,variant_inspection=variant_inspection,
            variant_movement=variant_movement,variant_performance=variant_performance,variant_export=variant_export,
            edited_source_rebuild=rebuilt,rollback_source_rebuild=rolled_back,
            edited_glb_byte_equal=rebuilt['model_sha256']==variant['model_sha256'],rollback_glb_byte_equal=rolled_back['model_sha256']==base['model_sha256'],
            real_same_slot_conflict_rejected=True,movie_performance_rejected=True,comparison_cameras_identical=True)
    except Exception as exc:
        report.update(status='failed',error=str(exc));raise
    finally:
        report['elapsed_seconds']=round(time.monotonic()-start,3)
        write(out/'e2e.json',report)
        print('KAI E2E:',out/'e2e.json',flush=True)


if __name__=='__main__':
    main()
