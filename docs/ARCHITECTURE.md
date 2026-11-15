# Existing architecture

0.2 extends the original factory; it does not replace its architecture.

| Component | Responsibility |
|---|---|
| `core.py` | Registration, revisions, staging/publication, hashes, process logs and capability policy |
| `cli.py` | ingest/build/edit/validate/preview/export/revise/checkout |
| `plugins.py` | Implemented local plugins and Python entry-point discovery |
| `glb.py` | Structure/geometry/material checks; skin and animation validation |
| `resources/blender_worker.py` | Static import, editable source, export and reimport |
| `resources/character_worker.py` | Existing rig/skin/actions preservation, bounded local edit, export/reimport |
| `resources/godot/` | Generic static preview and fixed-camera real skeletal animation preview |
| `profiles/` | Engine-independent export contracts |
| `skills/` | Explicitly installable Codex/Claude routing templates |

```text
assets/<asset-id>/
  asset.json
  raw/
  licenses/
  source/r0001/
  builds/<run-id>/
  edits/<run-id>/
  previews/<run-id>/
  exports/<run-id>/
  runs/<run-id>/
artifacts/
  failed_transactions/
  e2e/
  character_e2e/
  pbr_e2e/
```

Stages use the existing version directories and execution ledger. Failed ingest/revise cannot publish partial registration; failed files/logs are quarantined, and registered identities are never implicitly replaced. Asset production remains separate from any consuming game.

The core does not depend on Godot. Blender builds and GLB exports work without it; the optional preview reads the built GLB. Future Mod profiles extend export interfaces rather than adding game rules to registration.

Licenses independently record commercial use, modification, runtime distribution, source distribution and third-party upload. Export requires validated unchanged output plus sufficient rights for the selected usage. No upload/paid-generation backend is implemented. Plugin metadata is not an OS security sandbox.

Static import rejects skin/animation instead of stripping it. The verified character profile supports up to four influences per vertex, existing compatible rigs and existing actions. Morph targets and unsupported influence counts fail explicitly. Technical verification never grants visual approval.
