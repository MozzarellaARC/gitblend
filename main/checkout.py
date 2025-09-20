import bpy  # type: ignore
from .utils import (
    get_gitblend_dir,
    load_commit_metadata
)


class GITBLEND_OT_Checkout(bpy.types.Operator):
    """Checkout a specific commit."""
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_description = "Checkout a specific commit and restore data blocks"
    bl_options = {'REGISTER', 'UNDO'}
    
    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Hash of the commit to checkout"
    )
    
    def execute(self, context):
        try:
            # Check if git_blend is initialized
            gitblend_dir = get_gitblend_dir()
            if not gitblend_dir.exists():
                self.report({'ERROR'}, "Git Blend not initialized.")
                return {'CANCELLED'}
            
            # Load metadata
            metadata = load_commit_metadata(gitblend_dir)
            
            if self.commit_hash not in metadata.get("commits", {}):
                self.report({'ERROR'}, f"Commit {self.commit_hash} not found")
                return {'CANCELLED'}
            
            commit_data = metadata["commits"][self.commit_hash]
            blend_file = commit_data.get("blend_file")
            
            if not blend_file:
                self.report({'ERROR'}, "No blend file associated with this commit")
                return {'CANCELLED'}
            
            blend_filepath = gitblend_dir / blend_file
            if not blend_filepath.exists():
                self.report({'ERROR'}, f"Blend file {blend_file} not found")
                return {'CANCELLED'}
            
            # Get the exact state that should exist after checkout
            target_data_blocks = commit_data.get("data_blocks", {})
            
            # Step 1: Clear ALL existing data blocks (complete reset)
            self.clear_all_data_blocks()
            
            # Step 2: Append all data blocks from the commit
            success = self.append_commit_data_blocks(str(blend_filepath), target_data_blocks)
            
            if not success:
                self.report({'ERROR'}, "Failed to restore commit state")
                return {'CANCELLED'}
            
            # Update current commit in metadata
            metadata["current_commit"] = self.commit_hash
            from .utils import save_commit_metadata
            save_commit_metadata(gitblend_dir, metadata)
            
            self.report({'INFO'}, f"Checked out commit: {commit_data.get('message', self.commit_hash)}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to checkout commit: {str(e)}")
            return {'CANCELLED'}
    
    def clear_all_data_blocks(self):
        """Clear all data blocks to prepare for commit state reconstruction."""
        # Clear objects from scene first
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        
        # Clear all data blocks
        data_collections = [
            bpy.data.meshes,
            bpy.data.materials, 
            bpy.data.textures,
            bpy.data.images,
            bpy.data.actions,
            bpy.data.node_groups,
            bpy.data.texts
        ]
        
        for collection in data_collections:
            for item in list(collection):
                try:
                    collection.remove(item)
                except:
                    # Some items might be in use and can't be removed
                    pass
    
    def append_commit_data_blocks(self, blend_filepath: str, target_data_blocks: dict) -> bool:
        """Append all data blocks from the commit to reconstruct the exact state."""
        try:
            # Use bpy.ops.wm.append with proper directory structure
            # First, let's append everything from the blend file
            
            # Get list of all data types and their names from target_data_blocks
            append_operations = [
                ("Object", target_data_blocks.get("objects", [])),
                ("Mesh", target_data_blocks.get("meshes", [])),
                ("Material", target_data_blocks.get("materials", [])),
                ("NodeTree", target_data_blocks.get("node_groups", [])),
                ("Text", target_data_blocks.get("texts", [])),
                ("Action", target_data_blocks.get("actions", [])),
                ("Image", target_data_blocks.get("images", []))
            ]
            
            for data_type, data_list in append_operations:
                if not data_list:
                    continue
                    
                for item_info in data_list:
                    item_name = item_info.get("name", "")
                    if not item_name:
                        continue
                    
                    try:
                        # Construct the filepath for this specific data block
                        item_filepath = f"{blend_filepath}/{data_type}/{item_name}"
                        directory = f"{blend_filepath}/{data_type}/"
                        
                        bpy.ops.wm.append(
                            filepath=item_filepath,
                            directory=directory,
                            filename=item_name,
                            link=False,
                            autoselect=False,
                            active_collection=True,
                            instance_collections=False,
                            instance_object_data=True,
                            set_fake=False,
                            use_recursive=True
                        )
                        
                    except Exception as e:
                        print(f"Warning: Could not append {data_type} '{item_name}': {e}")
                        continue
            
            return True
            
        except Exception as e:
            print(f"Error in append_commit_data_blocks: {e}")
            return False