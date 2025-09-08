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
- Do not use realtime tracking in any situation whatsoever.
- All diff io should not use a full scene copy.
- Use validation.py to handle common safeguards and checks.
- Use git_utils.py to handle all git and git-lfs related operations.