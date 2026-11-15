# Game Asset Factory

- Read README.md and docs/ARCHITECTURE.md. Extend the existing CLI, plugins, revisions and execution ledger; do not introduce a parallel factory or Agent framework.
- Keep production independent of game projects. Never modify another game's project or revive frozen generators while working on this factory.
- Preserve raw files, editable sources, license evidence, recipes, failed and successful logs, builds, previews and exports. New operations create immutable version directories.
- Run `uv run --locked pytest -q`. Download the pinned real samples first as described in README.md. Integration changes also require real Blender/Godot/FFmpeg E2E; mocks are not substitutes.
- Technical checks do not approve visual quality. Keep `visual_review=pending_human`; agents cannot grant art approval.
- Verify commercial use, modification, runtime distribution, source distribution and third-party upload independently. MIT covers factory code, not third-party assets.
- No automatic uploads, paid API calls or purchases. External plugins are trusted local code, not an OS sandbox.
- 0.3 extends the same character plugins with explicit Morph preservation, equipment components, third-person preview and independent performance sampling. See docs/v03/WORKFLOW.md. KAI originally has one mesh/material and no Morphs or separate equipment; retain the distinction between original content, licensed Kenney parts and newly authored facial keys/action. Do not claim automatic rigging, arbitrary retargeting, 2D production or Mod adapters.
- Keep local asset databases, runs, credentials, caches and machine configuration out of public history. Use Git LFS for deliberately published binary assets after checking their licenses and metadata.
