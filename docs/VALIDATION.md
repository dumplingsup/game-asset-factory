# Public-source validation, 0.2

This is the retained historical 0.2 record. Current 0.3 results, regression reruns, real biped/Morph/equipment evidence and limits are recorded in [v03/VALIDATION.md](v03/VALIDATION.md).

The public checkout was tested again on 2026-11-15 using actual pinned Fox/Lantern files, Blender 5.2.3, Godot 4.7.2 and FFmpeg. Core production modules are unchanged from the local 0.2 implementation. Publishing adds portable setup/documentation, explicit license/recipe arguments to the old static E2E, a pinned default sample download and a portable skill installer.

| Check | Actual result |
|---|---|
| Python contracts + real Fox format checks | 36 passed |
| PBR E2E | 12 steps passed; Lantern, 3 Mesh, 1 material, 4 images |
| Character E2E | 19 steps passed; 24 joints, 3 real clips |
| Original static E2E with explicit Lantern license/recipe | 18 steps passed |
| Portable skill installation | Four files installed in a sandbox home; existing text preserved; actual rollback restored the prior state; live host skills untouched |
| Skill templates | Both passed the skill validator |
| Videos | Two character MP4s and PBR MP4 fully decoded |

Real character E2E imports skin/rig/material/actions, saves editable .blend, modifies 15 of 1,728 vertices in the left-ear region, registers r0002, exports and validates GLB, then reloads a saved baseline motion library from disk onto the variant in Godot. UV, weights, bones, action curves, material nodes and packed images retain their protected digests. Run, Survey and Walk drive actual joints and baked skinned vertices. Original and edited source rebuilds each produced byte-identical GLBs to their corresponding first build.

Machine-independent summaries: [character](validation/character.json), [PBR](validation/pbr.json), [static regression](validation/static.json). These are explicitly summaries, not replacement integrity receipts. Full local commands/stdout/stderr and immutable asset files remain in ignored assets/artifacts. Re-run the README commands to generate your own complete evidence.

Actual final keyframes were opened: the full textured Fox is visible in a running pose; Lantern shows its textured structure and emissive lamp. These observations and successful decoding do not grant aesthetic approval. `visual_review=pending_human` throughout.

The character profile supports existing compatible rigs, at most four influences per vertex, and no morph targets. It does not prove arbitrary constraint/driver preservation, automatic rigging or cross-rig retargeting. GLB animation export samples at 60 Hz in this test: Run 1.15833→1.15 s and Walk 0.70833→0.7 s, each within one frame. Original curves remain in .blend. Materials/motion/performance for arbitrary production characters still require real target-specific tests and human visual review.

GitHub Actions runs the 36 Python/real-model format checks after explicitly acquiring the pinned samples. It does not install Blender/Godot or claim E2E/visual acceptance on a hosted runner. The full production E2E above was executed locally with real tools.

The public Git history retains the original source-change sequence while omitting private asset databases, evaluation snapshots and machine-specific paths. Source-only filtering changes commit IDs and removes commits that only recorded private artifacts; it does not rewrite the original local repository or evaluation ZIP.
