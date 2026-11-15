"""Install the shared factory skill + focused routing edit; retain exact rollback data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {'codex': Path.home() / '.codex/skills', 'claude': Path.home() / '.claude/skills'}
ALLOWED = {str((directory / skill / 'SKILL.md').resolve()) for directory in HOSTS.values() for skill in ('game-asset-factory', 'game-art-workflow')}


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def routed(payload):
    text = payload.decode('utf-8-sig')
    description = '为个人独立游戏与各类 Mod 制作或修改美术素材时，优先复用本地 Game Asset Factory 管理许可、静态 PBR 和带骨架动画的角色加工、局部修改、预览与导出；2D、像素特效等使用对应专用工作流。'
    text = re.sub(r'(?m)^description: .+$', 'description: ' + description, text, count=1)
    old = '按当前任务选用本机工具。同级技能目录提供 SKILL.md；下列 PowerShell 路径使用当前用户的主目录。原始规格、绘图脚本及导出文件放在所做游戏的项目中。'
    new = '按当前任务选用本机工具。同级技能目录提供 SKILL.md；下列 PowerShell 路径使用当前用户的主目录。共享生产素材的原件、可编辑文件、许可和版本优先保存在独立工厂；游戏／Mod 工程接收派生导出件。用户指定的路径和既有工程约束优先。'
    text = text.replace(old, new)
    block = '''<!-- game-asset-factory-routing:start -->
## 优先使用本地资产工厂

先读取同级 `game-asset-factory/SKILL.md`。仓库位于 `{{FACTORY_ROOT}}`；从任何目录调用均显式指定 `uv --project` 和 `gaf --root`，避免写入游戏项目。静态 3D 的 ingest → build → validate → preview → export 优先走该 CLI，保留许可证、源修订、真实工具日志和导出版本。技术通过不能替代人工视觉评审。

工厂 0.3 支持既有骨架／蒙皮／材质／动画保留、显式 Morph 保留、同步目标的局部修改、兼容 rig 动作复用、装备组件与第三人称检视；角色必须使用角色插件。预览配置与真实 KAI 派生样本见工厂 docs/v03/WORKFLOW.md；原 KAI 与新制面部／装备内容分别溯源。当前不支持自动绑定、任意骨架 retarget、2D 生产、付费生成服务或具体游戏的 Mod 导出；按实际能力转交专用工具。禁止把权利未核验的素材上传生成服务。直接 Blender 脚本可作为专用加工补充，成熟后通过插件接入工厂。
<!-- game-asset-factory-routing:end -->'''
    text = re.sub(r'<!-- game-asset-factory-routing:start -->.*?<!-- game-asset-factory-routing:end -->\s*', '', text, flags=re.S)
    text = text.replace('- 角色、道具、地块和逐帧动画用 pixel-art-studio。', '- 2D 角色、道具、地块和逐帧动画用 pixel-art-studio。')
    heading = '# 游戏美术工作流'
    if heading not in text:
        raise ValueError('Expected existing workflow heading missing; refusing broad rewrite')
    return text.replace(heading, heading + '\n\n' + block.replace('{{FACTORY_ROOT}}', ROOT.as_posix()), 1).encode('utf-8')


parser = argparse.ArgumentParser()
parser.add_argument('--rollback', type=Path)
args = parser.parse_args()
if args.rollback:
    record = json.loads(args.rollback.read_text(encoding='utf-8'))
    for entry in record['files']:
        path = Path(entry['path']).resolve()
        if str(path) not in ALLOWED:
            raise ValueError('Rollback target not allowlisted')
        if not path.is_file() or digest(path.read_bytes()) != entry['after_sha256']:
            raise ValueError('Skill changed since install; refusing rollback overwrite: ' + str(path))
    for entry in record['files']:
        path = Path(entry['path'])
        if entry['before_backup']:
            payload = Path(entry['before_backup']).read_bytes()
            if digest(payload) != entry['before_sha256']:
                raise ValueError('Backup hash mismatch')
            path.write_bytes(payload)
        else:
            path.unlink()
    print(json.dumps({'status': 'rolled_back', 'record': str(args.rollback)}))
else:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    backup = ROOT / 'artifacts/skills_backup' / stamp
    backup.mkdir(parents=True)
    master = (ROOT / 'skills/game-asset-factory/SKILL.md').read_bytes().replace(b'{{FACTORY_ROOT}}', ROOT.as_posix().encode('utf-8'))
    planned = []
    for host, directory in HOSTS.items():
        workflow = directory / 'game-art-workflow/SKILL.md'
        workflow_payload = workflow.read_bytes() if workflow.is_file() else (ROOT / 'skills/game-art-workflow/SKILL.md').read_bytes()
        planned.extend([(host, directory / 'game-asset-factory/SKILL.md', master), (host, workflow, routed(workflow_payload))])
    record = {'installed_at': datetime.now(timezone.utc).isoformat(), 'files': []}
    for host, path, payload in planned:
        before = path.read_bytes() if path.is_file() else None
        before_backup = backup / (host + '-' + path.parent.name + '.md') if before is not None else None
        if before_backup:
            before_backup.write_bytes(before)
        record['files'].append({'path': str(path), 'before_backup': str(before_backup) if before_backup else None,
                                'before_sha256': digest(before) if before is not None else None, 'after_sha256': digest(payload)})
    (backup / 'install.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for _, path, payload in planned:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    summary = {'status': 'installed', 'record': str(backup / 'install.json'), 'files': [{'path': entry['path'], 'sha256': entry['after_sha256']} for entry in record['files']]}
    (ROOT / 'artifacts/skill_install.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
