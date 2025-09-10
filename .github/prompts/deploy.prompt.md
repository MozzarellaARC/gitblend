---
mode: agent
---
# Deployment Instructions
- Deployment using powershell script
- The script should handle:
    - zip compression into dist/
    - zip name uses the id and version from blender_manifest.toml
    - exclude unnecessary files and directories .git, .vscode, __pycache__, .github, .gitignore, README.md
- The script lives in .vscode/deploy.ps1