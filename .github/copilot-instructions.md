# Project Guidelines

## Scope
- These instructions apply to the main Prompt Generator app in this repository.
- StableDiffusionClient is in scope for edits when needed for integration.
- Treat Stable Diffusion Forge internals as external/vendor code unless a task explicitly targets them.
- Do not broadly refactor or restyle files under StableDiffusionClient/stable-diffusion-webui-forge unless requested.

## Build and Run
- Main app (Windows): run run_app.bat from repository root.
- Main app (manual): activate .venv, then run python main.py.
- StableDiffusion client integration: use run_sdc_manualy.bat from repository root, or run StableDiffusionClient/start_all.bat from StableDiffusionClient.
- There is no canonical automated test suite in the main app yet.

## Architecture
- Entry point: main.py.
- UI orchestration: src/main_window.py and src/panels/.
- Data model: src/models.py (dataclasses).
- Persistence: src/database.py (SQLite).
- Prompt logic: src/prompt_generator.py.
- Batch/task execution bridge: src/batch_runner.py and src/generation_worker.py.

## Conventions
- Keep existing typing style and dataclass-driven model patterns.
- Preserve PySide signal/slot boundaries between UI components.
- Follow existing Japanese UI/messages/comments where already used.
- Prefer focused edits in the main app (main.py, src/) first, then StableDiffusionClient integration files when necessary.
- Avoid modifying stable-diffusion-webui-forge internals unless explicitly requested.

## Pitfalls
- Keep DB path normalization behavior in main.py (backslash to slash conversion for stored db_path).
- Maintain relative-path assumptions used by batch and client launch scripts.
- Avoid blocking UI paths when changing generation process handling; generation execution is thread-based.

## Documentation
- Project overview and conventions: GEMINI.md.
- StableDiffusion client usage details: StableDiffusionClient/README.md and scripts under StableDiffusionClient/.
