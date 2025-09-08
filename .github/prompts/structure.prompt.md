---
mode: agent
---
# Dependencies Directory
- `"C:\Program Files\Git\bin\git.exe"`
- `"C:\Program Files\Git LFS\git-lfs.exe"`

# Addon Project Structure
- parent
    - __init__.py
    - blender_manifest.toml
    - .github/
        - prompts/
            - structure.prompt.md
            - core.prompt.md
            - ui.prompt.md
    - .vscode/
        - ...
    - headless/
        - __init__.py
        - h_commit.py
        - h_diffing.py
        - h_signatures.py
    - main/
        - __init__.py
        - operators.py
    - pref/
        - __init__.py
        - properties.py
        - preferences.py
        - panel.py
    - ui/
        - __init__.py
        - main_panel.py
    - utils/
        - __init__.py
        - ...

# Working .blend Structure
- ***working repo***
    current.blend
    - .gitblend/
        - template.blend
        - .git/
        - .gitattributes
        - .gitignore
        - ... etc.