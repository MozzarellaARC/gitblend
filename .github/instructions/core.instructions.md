---
applyTo: '**'
---
# Commit Architecture

***Glossary:***
- .gitblend: the folder where all the blend file snapshots are stored
- scene src: the current working scene

## Overview
- When commit operator gets executed:
    - use bpy.ops.wm.save_as_mainfile to save the current scene to .gitblend directory
    - .gitblend directory should be in the same level as the the current working .blend file
    - the saved file name should be a unique identifier using sha-256