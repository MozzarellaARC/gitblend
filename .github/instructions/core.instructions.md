---
applyTo: '**'
---
# Commit Architecture

***Glossary:***
- .gitblend: the folder where all the blend file snapshots are stored
- scene src: the current working scene

## Concept
An SCM like version control system but for binaries and deals with .blend files specifically, by saving delta changes of the indvidual bpy.data blocks.

## Technical Initialize
- When the initialize operator gets executed:
    - generate .gitblend directory on the same level as the .blend file, with validation:
        - if .gitblend already exists, throws info message and aborts
        - generate .json metadata of the initial commit with:
            - commit hash
            - timestamp
            - commit message (from operator input)
            - parent commit hash (null for initial commit)
    - generate .blend file using sha-256 of the indvidual .blend content using bpy.data.libraries.write
    - the bpy.data.libraries.write should include bpy.data blocks from `data.instructions.md`

## Technical Commit
- When commit operator gets executed:
    - validate if .gitblend exists, if not, throws error message and aborts
    - export data blocks included in `data.instructions.md` to .gitblend
    - append json metadata file in .gitblend with:
        - commit hash
        - timestamp
        - commit message (from operator input)
        - parent commit hash (if exists)
    - generate .blend file using sha-256 of the indvidual .blend content using bpy.data.libraries.write
    - diff the new .blend file with the previous commit/initial .blend file
        - if no changes, throws info message and aborts
        - if changes, keep the new .blend file and update the metadata json file with the new commit hash