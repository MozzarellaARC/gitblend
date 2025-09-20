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
- read the JSON file for subsequent commits to determine which data blocks to export
- for subsequent commits if a data block already exists in the JSON file:
    - if modified (export again and update the pointer in the JSON file) and mark as modified
    - if not modified (do not export and parse the previous pointers into the JSON file)


# Checkout Architecture
- read the JSON file in the .gitblend directory
- for each data block pointer in the JSON file:
 	- check if the data block already exists in bpy.data
 	- if it does not exist, import data block
 	- if it does exist, overwrite data block
- utilize bpy.ops.wm.append to import data blocks from the .gitblend directory