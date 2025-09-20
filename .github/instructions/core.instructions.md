---
applyTo: '**'
---
# Commit Architecture
- generate .gitblend directory on the same level as the current .blend file directory
- utilize `bpy.data.libraries.write` to export .blend data
- .blend file name uses sha-256 hash