# Third-party notices

Root MIT covers the factory's own code/documentation. It does not relicense third-party models, textures, animations, license texts or upstream README files.

## Pinned Khronos samples

https://github.com/KhronosGroup/glTF-Sample-Assets at commit `8f492390ddc7a2ae221a1369ef560589cf8c70fb`.

| Model | Authors and terms | Evidence |
|---|---|---|
| Fox | PixelMannen model: CC0-1.0. tomkranis rigging/animation and AsoboStudio/scurest glTF conversion: CC-BY-4.0. | `vendor/khronos-fox/8f492390ddc7/` |
| Lantern | Microsoft/sbtron; compression by Frank Galligan. CC0-1.0. | `vendor/khronos-lantern/8f492390ddc7/` |

The explicit download script retrieves actual models locally. Preserve upstream attribution, license links and modification notices when distributing derivatives. Exports carry notices. Do not label the whole Fox CC0.

## Optional original static record

`examples/cc0-human.license.json` describes Blender Studio Human Base Meshes 1.4.1, selected GEO-body_male_realistic, CC0-1.0. The selected binary is not included. The embedded bundle README and source record remain as evidence; do not reuse their identity for unrelated models. The original static E2E now accepts explicit license/recipe files and can run on Lantern.

## v0.3 character sources

KAI — The Little Fox Warrior (Animated), by Realidad Aumentada Empezando Desde Cero, [official source](https://sketchfab.com/3d-models/aa56e447b578470b8d6b1b9587fd29ac), [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Credit the author, retain source/license links and identify modifications. No endorsement implied. Original KAI contains a rig and eight clips, no separate equipment or facial Morphs. This iteration adds two facial keys, an expression clip, equipment fitting, orientation and a bounded ear edit. The source download and derivative binaries are retained locally, not included under the factory MIT license.

Kenney [Mini Dungeon 2.0](https://kenney.nl/assets/mini-dungeon): CC0, actual sword/spear/shield meshes and colormap texture. Exact archives, dependency hashes and license text remain with local asset records.

Wolfman / Polygonal Mind, 100Avatars R1: CC0 according to the original VRM metadata and [pinned source registry](https://github.com/ToxSam/open-source-avatars/blob/0f9a1b2fd99894736563d55b2c9dc9125700d081/data/avatars/100avatars-r1.json). Used only for real Morph-format regression; it has no original animation. The explicit acquire script retains primary source records and checks the exact binary hash. This does not certify VRM runtime/MToon/spring-bone semantics.

## Dependencies/tools

Python dependencies in pyproject.toml/uv.lock keep upstream licenses. Blender, Godot, FFmpeg, uv, Python and Git LFS are external tools; their binaries are not included or relicensed.

Sample `third_party_upload` remains false for automatic service uploads. A license allowing distribution does not authorize an Agent to send unrelated user assets to an AI service. No such production backend exists here.
