# Git Blend – Git-like SCM/VCS for Blender pipeline

Purpose: Utilize Git like version control concepts within Blender, leveraging Git and Git LFS for storage, while adhering to Blender's architecture and conventions.

## Project Structure
- look at structure.prompt.md

## Core Architecture
- look at core.prompt.md

## UI Architecture
- look at ui.prompt.md

## Diff Architecture
- Commit operates from a headless instance of Blender
    - headless instance spawned from the operator
    - headless instance runs in background mode
    - headless instance path `"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"`
    - headless instance appends selected object from current instance of Blender (not headless)
    - headless instance saves to a new `.blend` file