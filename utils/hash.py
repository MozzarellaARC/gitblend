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
        
        # Read only stable sections of the file for hashing
        with open(temp_filepath, 'rb') as f:
            # Hash the first 1000 bytes (header and stable data)
            stable_header = f.read(1000)
            hash_to.update(stable_header)
            
            # Skip the variable section (bytes 1000-31000)
            # Hash some later stable sections
            f.seek(35000)  # Skip past the variable data
            if f.tell() < os.path.getsize(temp_filepath):
                stable_middle = f.read(10000)  # Read 10KB from stable section
                hash_to.update(stable_middle)
            
            # Hash the last stable section
            file_size = os.path.getsize(temp_filepath)
            if file_size > 50000:
                f.seek(-10000, 2)  # Last 10KB
                stable_end = f.read(10000)
                hash_to.update(stable_end)
                
        total_bytes_hashed = len(stable_header)
        if 'stable_middle' in locals():
            total_bytes_hashed += len(stable_middle)
        if 'stable_end' in locals():
            total_bytes_hashed += len(stable_end)
            
        print(f"Total bytes hashed: {total_bytes_hashed} (truncated from {os.path.getsize(temp_filepath)})")
        print(f"Header bytes: {len(stable_header)}")
                
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