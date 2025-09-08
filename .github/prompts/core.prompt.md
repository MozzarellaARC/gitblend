---
mode: agent
---
# Core Architecture
- A git like vcs, that utilize git and git-lfs binaries.
- Each important module should be on the subpackages.
- Sub-packages:
    - `main/`: most important logic and functionality.
    - `pref/`: addon preferences
    - `utils/`: utility functions and shared helpers.
- All subpackages should have an __init__.py file where modules are registered and unregistered.
- Do not register and unregister on the module level.