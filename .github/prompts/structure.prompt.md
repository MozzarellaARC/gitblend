---
mode: agent
---
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
    - main/
        - __init__.py
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
    - .gitblend/
        - template.blend
        - .git/
        - .gitattributes
        - .gitignore
        - ... etc.