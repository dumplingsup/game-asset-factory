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

## Dependencies/tools

Python dependencies in pyproject.toml/uv.lock keep upstream licenses. Blender, Godot, FFmpeg, uv, Python and Git LFS are external tools; their binaries are not included or relicensed.

Sample `third_party_upload` remains false for automatic service uploads. A license allowing distribution does not authorize an Agent to send unrelated user assets to an AI service. No such production backend exists here.
