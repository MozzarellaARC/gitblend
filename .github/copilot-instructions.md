# Git Blend – Git-like SCM/VCS for Blender pipeline

Purpose: Utilize Git like version control concepts within Blender, leveraging Git and Git LFS for storage, while adhering to Blender's architecture and conventions.

## General Guidelines to Follow
- for directories and overall file package structure please look at structure.prompt.md
- for the main concept and visionary please look at core.prompt.md
- for UI design and layout considerations please look at ui.prompt.md

## Diff Architecture
- Commit operates from a headless instance of Blender
    - headless instance spawned from the operator
    - headless instance runs in background mode
    - headless instance path `"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"`
    - headless instance appends selected object from current instance of Blender (not headless)
    - headless instance saves to a new `.blend` file

## Specifics
- bpy will always be available no matter what, do not try/except around bpy