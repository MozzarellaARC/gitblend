# Git Blend – Git-like SCM/VCS for Blender pipeline

Purpose: Utilize Git like version control concepts within Blender, leveraging Git and Git LFS for storage, while adhering to Blender's architecture and conventions.

# Environment
- Blender 4.2 to 4.5

## General Guidelines to Follow
- for directories and overall file package structure please look at structure.prompt.md
- for the main concept and visionary please look at core.prompt.md
- for UI design and layout considerations please look at ui.prompt.md

## Diff Architecture
- Commit/Initialize operator spawn a headless instance of Blender
    - The headless instance uses the latest commit as the working file
    - If there is no commit, the headless instance uses template.blend as the working file
    - The headless instance append UID to the suffix of every data-block exists in the working file, if there are already UIDs, it will not append another UID
    - The headless instance append the scene from the current Blender instance
    - The headless instance then resolve the diff between the two scenes, and delete hierarchically all data-blocks that are identical

## Checkout Architecture
- Checkout spawns a headless instance of Blender
    - The headless instance uses the selected commit on the list as the working file
    - The headless instance resolve and rebuilds the scene based on the available diff .blend and .json up to the selected commit
    - The headless instance then saves the rebuilt scene as a temporary .blend file
    - Checkout then replaces the current scene in the current Blender instance with the rebuilt scene

## Specifics
- bpy will always be available no matter what, do not try/except around bpy