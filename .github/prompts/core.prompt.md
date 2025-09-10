---
mode: agent
---
# Core Architecture
- A git like vcs, that utilize git and git-lfs binaries.
- There should be no stray properties
- All properties should be stored inside PropertyGroup except for the properties unrelated to bpy
- Each important module should be on the subpackages.
- Sub-packages:
    - `main/`: most important logic and functionality.
    - `pref/`: addon preferences
    - `utils/`: utility functions and shared helpers.
- All subpackages should have an __init__.py file where modules are registered and unregistered.
- Do not register and unregister on the module level.
- Do not use modal operators or timer based update handlers.