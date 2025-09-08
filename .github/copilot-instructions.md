# Git Blend – Git-like SCM/VCS for Blender pipeline

Purpose: Utilize Git like version control concepts within Blender, leveraging Git and Git LFS for storage, while adhering to Blender's architecture and conventions.

## Best practices for prompting
- Check for prompts in `.github/prompts/` for specific guidelines.

## Big picture (read first)
- Dual storage model (see ARCHITECTURE.md):
    - Scene duplicates for diffing snapshots
    - Git for metadata and Git LFS for .blend snapshots.

## Key files and roles
- `__init__.py`: central register/unregister; imports register helpers from `main/*`.
- `main/operators.py`: operators (initialize, commit, undo, discard, checkout) and restore flow.
- `utils/validate.py`: snapshot creation (delta-only), equality checks, name/UID rules.
- `main/signatures.py`: object/collection signatures + `derive_changed_set`.
- `main/cas.py`: commit creation, refs, and branch history traversal.
- UI: `prefs/panel.py` (panel) + `prefs/properties.py` (branch list, change log, UI state).

## Conventions you must follow
- Registration is centralized: do not register/unregister module at top level packages; expose `register_*`/`unregister_*` in modules and wire in `__init__.py` (see `.github/prompts/core.prompt.md`).
- Do not use modal operators or timer based update handlers.
- All properties must be stored inside PropertyGroup except for the properties unrelated to bpy (see `.github/prompts/core.prompt.md`).
- Use a single panel class for all UI (see `.github/prompts/ui.prompt.md`).
- Use collapsible boxes to separate function categories in the UI (see `.github/prompts/ui.prompt.md`).
- Follow Blender's naming conventions for operators, classes, and properties.

## Confirmation
- Any debugging related code must be asked and confirmed with me before being added.
- Never ask for anything related to legacy code or deprecated libraries, just remove immediately.