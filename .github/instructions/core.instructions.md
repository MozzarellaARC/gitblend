---
applyTo: '**'
---
# Commit Architecture

***Glossary:***
- .gitblend: the folder where all the blend file snapshots are stored
- scene src: the current working scene

when executing commit operator, the current blender instance will create a new blender headless mode instance and perform operations there, with the following steps:
    1. Create a new blend file snapshot in the .gitblend folder
    2. Append the current scene src
    3. Save the new blend file snapshot into the .gitblend folder
    4. .gitblend folder should be on the same directory level as the blend file being worked on