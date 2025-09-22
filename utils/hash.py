import bpy
import hashlib
import tempfile
import os

SHA256 = hashlib.sha256

def blend_file_hash(filepath):
    """Compute the SHA-256 hash of exported objects using bpy.data.libraries.write."""
    hash_to = SHA256()
    
    # Create a temporary file for export
    with tempfile.NamedTemporaryFile(suffix='.blend', delete=False) as temp_file:
        temp_filepath = temp_file.name
    
    try:
        # Collect all datablocks to export (skip orphan data)
        datablocks = set()
        
        # Add all objects and their data (objects are always considered used)
        for obj in bpy.data.objects:
            datablocks.add(obj)
            if obj.data and obj.data.users > 0:
                datablocks.add(obj.data)
            
        # Export using bpy.data.libraries.write
        bpy.data.libraries.write(temp_filepath, datablocks, compress=False)
        
        # Read the exported file and compute hash
        with open(temp_filepath, 'rb') as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                hash_to.update(byte_block)
                
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
    
    return hash_to.hexdigest()

class GITBLEND_OT_Serde(bpy.types.Operator):
    bl_idname = "gitblend.serde"
    bl_label = "Git Blend Serde"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Get all object and their data
    def execute(self, context):
        print(blend_file_hash(bpy.data.filepath))
        return {'FINISHED'}