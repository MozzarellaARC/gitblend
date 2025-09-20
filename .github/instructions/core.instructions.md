---
applyTo: '**'
---

# Initialize / Sync Architecture
- create the .gitblend directory on the same level as the current .blend file directory
- export the existing data blocks into the .gitblend directory
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
- serialize the data block that gets exported into a JSON file in diffable format
- use the .blend file hash as the key in the JSON file and the value is the pointers to the data blocks that were exported

# Diffing Architecture
- data blocks to diff:
 	- compare json to bpy.data.objects
        - simple transform (location, rotation, scale) diff
        - simple name and size diff
 	- compare json to bpy.data.meshes
        - simple transform (location, rotation, scale) diff
        - samples the vertices up to 1000 vertices for performance
 	- compare json to bpy.data.materials
        - sample the node count
 	- compare json to bpy.data.images
        - simple name and size diff
 	- compare json to bpy.data.texts
        - simple name and content diff
 	- compare json to bpy.data.actions
        - simple name and fcurves count diff
 	- compare json to bpy.data.node_groups
        - sample the node count

# Commit Architecture
- gatekeep the commit with Diffing Architecture
- utilize `bpy.data.libraries.write` to export .blend data blocks - delta
- .blend file name uses sha-256 hash
- data blocks - delta to export:
 	- bpy.data.objects
 	- bpy.data.meshes
 	- bpy.data.materials
 	- bpy.data.images
 	- bpy.data.texts
 	- bpy.data.actions
 	- bpy.data.node_groups
- serialize the data block - delta that gets exported into a JSON file in diffable format
- use the .blend file hash as the key in the JSON file and the value is the pointers to the data blocks - delta that were exported
- read the JSON file for subsequent commits to determine which data blocks to export
- for subsequent commits if a data block already exists in the JSON file:
    - if modified (export again and update the pointer in the JSON file) and mark as modified
    - if not modified (do not export and parse the previous pointers into the JSON file)

# Checkout Architecture
- read the JSON file in the .gitblend directory
- reconstruct the delta data blocks in the current .blend file based on the JSON file.
- make sure to recursive purge when deleting data blocks
- if delta reconstruction is successful, proceed to import
- utilize bpy.ops.wm.append to import data blocks from the .gitblend directory