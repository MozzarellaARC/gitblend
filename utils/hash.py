import bpy
import hashlib
import tempfile
import os

SHA256 = hashlib.sha256

def blend_file_hash(filepath):
    """Compute the SHA-256 hash of exported objects using truncated bytes."""
    hash_to = SHA256()
    
    # Create a temporary file for export
    with tempfile.NamedTemporaryFile(suffix='.blend', delete=False) as temp_file:
        temp_filepath = temp_file.name
    
    try:
        # Collect all datablocks to export (skip orphan data)
        datablocks_list = []
        
        # Add all objects and their data (objects are always considered used)
        for obj in sorted(bpy.data.objects, key=lambda x: x.name):
            datablocks_list.append(obj)
            if obj.data and obj.data.users > 0:
                datablocks_list.append(obj.data)
        
        # Sort datablocks by name for consistency
        datablocks_list.sort(key=lambda x: x.name if hasattr(x, 'name') else str(x))
        
        print(f"Exporting {len(datablocks_list)} datablocks:")
        for db in datablocks_list:
            print(f"  - {type(db).__name__}: {getattr(db, 'name', 'unnamed')}")
        
        # Convert to set for the API call
        datablocks = set(datablocks_list)
            
        # Export using bpy.data.libraries.write
        bpy.data.libraries.write(temp_filepath, datablocks, compress=False)
        
        # Read only the most stable section of the file for hashing
        with open(temp_filepath, 'rb') as f:
            # Hash only the first 1000 bytes (header and stable data)
            # This is the most reliable section that showed no variation
            stable_header = f.read(30000)
            hash_to.update(stable_header)
            
            # Add file size as additional discriminator
            file_size = os.path.getsize(temp_filepath)
            hash_to.update(file_size.to_bytes(8, byteorder='big'))
            
            # Add datablock count as additional discriminator
            datablock_count = len(datablocks_list)
            hash_to.update(datablock_count.to_bytes(4, byteorder='big'))
                
        total_bytes_hashed = len(stable_header) + 8 + 4  # header + file_size + count
            
        print(f"Total bytes hashed: {total_bytes_hashed} (header + file_size + count)")
        print(f"Header bytes: {len(stable_header)}, File size: {file_size}, Datablock count: {datablock_count}")
                
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