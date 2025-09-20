import bpy
import json
from .utils import (
    get_blend_file_hash,
    ensure_gitblend_dir,
    export_data_blocks_to_blend,
    serialize_data_blocks,
    save_commit_metadata
)


class GITBLEND_OT_Initialize(bpy.types.Operator):
    """Initialize Git Blend for the current .blend file."""
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Initialize Git Blend for the current .blend file"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            # Ensure blend file is saved
            if not bpy.data.filepath:
                self.report({'ERROR'}, "Please save the .blend file before initializing git_blend")
                return {'CANCELLED'}
            
            # Create .gitblend directory
            gitblend_dir = ensure_gitblend_dir()
            
            # Get file hash
            file_hash = get_blend_file_hash()
            
            # Collect data blocks to export
            data_blocks_dict = {
                "objects": list(bpy.data.objects),
                "meshes": list(bpy.data.meshes),
                "materials": list(bpy.data.materials),
                "images": list(bpy.data.images),
                "texts": list(bpy.data.texts),
                "actions": list(bpy.data.actions),
                "node_groups": list(bpy.data.node_groups)
            }
            
            # Flatten data blocks list for export
            all_data_blocks = []
            for blocks in data_blocks_dict.values():
                all_data_blocks.extend(blocks)
            
            # Export data blocks to .blend file
            if all_data_blocks:
                blend_filepath = export_data_blocks_to_blend(gitblend_dir, file_hash, all_data_blocks)
                self.report({'INFO'}, f"Exported {len(all_data_blocks)} data blocks to {blend_filepath}")
            
            # Serialize data blocks information
            serialized_data = serialize_data_blocks(data_blocks_dict)
            
            # Create initial commit metadata
            metadata = {
                "commits": {
                    file_hash: {
                        "data_blocks": serialized_data,
                        "blend_file": f"{file_hash}.blend",
                        "timestamp": bpy.context.scene.frame_current,  # Using frame as timestamp
                        "message": "Initial commit"
                    }
                },
                "version": 1,
                "current_commit": file_hash
            }
            
            # Save metadata
            save_commit_metadata(gitblend_dir, metadata)
            
            self.report({'INFO'}, f"Git Blend initialized successfully in {gitblend_dir}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to initialize git_blend: {str(e)}")
            return {'CANCELLED'}