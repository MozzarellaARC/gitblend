---
mode: agent
---
# Core Architecture
- There should be no stray properties
- All properties should be stored inside PropertyGroup except for the properties unrelated to bpy
- Each module category should be on the subpackages.
- Sub-packages:
    - `main/`: most important logic and functionality or operators.
    - `pref/`: addon preferences, UI, constants
    - `utils/`: utility functions and shared helpers.
- All subpackages should have an __init__.py file where modules are registered and unregistered.
- Do not register and unregister directly on the module.
- Do not use modal operators or timer based update handlers.