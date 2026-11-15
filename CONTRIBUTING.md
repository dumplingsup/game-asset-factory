# Contributing

Use Python 3.13 and `uv sync --locked`. Explicitly download pinned samples, then `uv run --locked pytest -q`. Integration changes need the real Blender/Godot/FFmpeg E2E commands in README.md using verified tools.

Extend existing CLI/plugin contracts; do not create a second factory or Harness. Preserve source/recipe/tool/code hashes, editable files, license evidence and failed logs. Refuse unsupported data rather than silently stripping it.

Keep private inputs, asset libraries, test output and machine configuration out of public commits. Published sample assets need exact sources/versions/hashes, rights and notices. Label test-only registration payloads; they are never E2E substitutes.

Describe behavior, actual validation and limits. Technical checks cannot approve visual quality. No automatic upload, paid provider integration or broad Mod-adapter work is implied by a plugin.

Factory code/documentation contributions are MIT; third-party materials retain their own terms/notices.
