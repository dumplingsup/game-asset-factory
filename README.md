# Game Asset Factory

A local, engine-independent asset pipeline for indie games and Mods. Python + uv orchestrates reproducible Blender jobs, editable source revisions, licensing, GLB validation and optional Godot previews. No Agent framework, cloud account or paid generation API is required.

本地游戏／Mod 美术资产工厂。**0.3** 在原有静态 PBR、骨架角色加工与兼容动作复用上，增加显式 Morph 保留、装备组件、第三人称检视和独立性能采样。资产生产独立于游戏工程；Godot 是通用预览目标。

v0.3: [scope and source distinctions](docs/v03/SCOPE.md), [reproduce the real KAI workflow](docs/v03/WORKFLOW.md), [technical results and remaining human review](docs/v03/VALIDATION.md).

**Status:** technical validation only. Every asset remains `visual_review=pending_human`; an Agent cannot approve visual quality. Automatic rigging, arbitrary retargeting, 2D production and game-specific Mod adapters are not implemented. KAI originally has no Morphs or separate equipment: this iteration explicitly authors facial keys and fits licensed Kenney equipment, preserving the original rig and eight clips.

## Requirements

Windows 11, Python 3.13 and [uv](https://docs.astral.sh/uv/). Verified integrations: Blender **5.2.3**, Godot **4.7.2**, FFmpeg. Other tool versions are not claimed compatible with this verified profile. Git LFS is used if you deliberately version binary assets.

Python CLI/contract tests do not need Blender or Godot. Production E2E needs actual tools. Set `BLENDER_BIN`, `GODOT_BIN`, `FFMPEG_BIN` to executable paths, or put the tools on PATH. Generated asset databases and test output are ignored by public Git.

## Quick start

```powershell
git clone https://github.com/dumplingsup/game-asset-factory.git
Set-Location game-asset-factory
uv sync --locked
uv run --locked python scripts/acquire_v02_samples.py
uv run --locked python scripts/acquire_v03_samples.py
uv run --locked pytest -q
uv run --locked gaf plugins
uv run --locked gaf doctor
```

The explicit acquisition commands download pinned Khronos Fox/Lantern and CC0 Wolfman Morph-format fixtures with license evidence through GET requests. They do not upload local files, read API keys or call a generation service. Wolfman has no original animation and is only a format regression fixture. KAI E2E requires the actual official ZIPs obtained normally; see the v0.3 workflow. Downloaded models are ignored by Git; preserved samples can be used offline.

### Real animated character

```powershell
uv run --locked gaf ingest my-fox --source vendor/khronos-fox/8f492390ddc7/Fox.glb --license-record examples/fox.license.json --recipe examples/fox.recipe.json
$base = uv run --locked gaf build my-fox --plugin blender-character | ConvertFrom-Json
uv run --locked gaf validate my-fox --build $base.build_id --plugin glb-character
uv run --locked gaf preview my-fox --build $base.build_id --plugin godot-character --material-mode source --movie
uv run --locked gaf export my-fox --build $base.build_id --usage commercial
```

Automated scripts must check each exit code before consuming JSON. See [the full character workflow](docs/CHARACTER_WORKFLOW.md) for a real local edit, source revision, original motion-library reuse on the edited rig and rebuild. Fox has 24 joints and Survey/Walk/Run. Its model is CC0; rigging/animation and conversion are CC-BY-4.0. Preserve attribution.

### Static PBR

```powershell
uv run --locked gaf ingest my-lantern --source vendor/khronos-lantern/8f492390ddc7/Lantern.glb --license-record examples/lantern.license.json --recipe examples/lantern.recipe.json
$built = uv run --locked gaf build my-lantern | ConvertFrom-Json
uv run --locked gaf validate my-lantern --build $built.build_id
uv run --locked gaf preview my-lantern --build $built.build_id --material-mode source --movie
uv run --locked gaf export my-lantern --build $built.build_id
```

## Data and reproducibility

`assets/<id>/` retains raw input, license evidence, editable source revisions, recipes, tool/code/input/output hashes, successful/failed logs, previews and exports. Use `revise` for new source versions and `checkout` for an earlier revision. Builds start from preserved source files.

Ingest/revise stage unpublished data and publish atomically. Failed transactions are quarantined and retryable. Source/sidecar names cannot overwrite internal metadata or implicitly replace inherited attachments. Export always requires runtime-distribution rights; commercial usage additionally requires commercial-use rights. Explicit noncommercial usage cannot bypass distribution rights.

When calling from a game/Mod directory, pass the factory checkout to both `uv --project` and `gaf --root`. Game projects receive exports, not the shared production database.

## Validation

```powershell
uv run --locked pytest -q
uv run --locked python tests/e2e_pbr.py
uv run --locked python tests/e2e_character.py
uv run --locked python tests/e2e.py --source vendor/khronos-lantern/8f492390ddc7/Lantern.glb --license-record examples/lantern.license.json --recipe examples/lantern.recipe.json --asset static-regression
```

E2E uses actual models, Blender, Godot and FFmpeg. Use a new ID when repeating the last command. Full local reports/stdout/stderr remain under ignored `artifacts/` and `assets/`. See [public validation records](docs/VALIDATION.md). Contract tests do not substitute for E2E or visual acceptance.

## Codex and Claude Code skills

Review and explicitly run `uv run --locked python scripts/sync_skills.py` to install the two `skills/` templates for both hosts. It inserts this checkout's absolute path into installed copies, preserves existing workflow text, records hashes/backups under ignored `artifacts/skills_backup/`, and supports `--rollback <install.json>`. Only the four named skill files change; ingest/build never trigger installation.

## Extension and licensing

Extend existing Python entry-point plugins: [architecture](docs/ARCHITECTURE.md), [plugins](docs/PLUGINS.md), [contributing](CONTRIBUTING.md). The dispatcher rejects network/upload/paid capabilities. Python plugins remain trusted code, not an OS sandbox.

Factory code/original documentation are [MIT](LICENSE). Third-party assets, license texts and upstream documentation keep their own terms: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Public availability is not a license. The public source history excludes private asset databases and machine-specific evaluation snapshots; the original development archive is retained separately.
