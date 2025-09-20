---
applyTo: '**'
---
# Commit Architecture
- generate .gitblend directory on the same level as the current .blend file directory
- utilize `bpy.data.libraries.write` to export .blend data blocks
- .blend file name uses sha-256 hash
- data blocks to export:
 	- bpy.data.objects
 	- bpy.data.meshes
 	- bpy.data.materials
 	- bpy.data.images
 	- bpy.data.texts
 	- bpy.data.actions
 	- bpy.data.node_groups
- serialize the data block that gets exported into a JSON file
- use the .blend file hash as the key in the JSON file and the value is the pointers to the data blocks that were exported