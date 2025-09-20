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
            
            # Clear existing data blocks that will be replaced
            data_blocks_to_restore = commit_data.get("data_blocks", {})
            
            # Remove existing data blocks that will be replaced
            for category, blocks_info in data_blocks_to_restore.items():
                if category == "objects":
                    collection = bpy.data.objects
                elif category == "meshes":
                    collection = bpy.data.meshes
                elif category == "materials":
                    collection = bpy.data.materials
                elif category == "images":
                    collection = bpy.data.images
                elif category == "texts":
                    collection = bpy.data.texts
                elif category == "actions":
                    collection = bpy.data.actions
                elif category == "node_groups":
                    collection = bpy.data.node_groups
                else:
                    continue
                
                # Remove existing blocks that will be replaced
                block_names = {block_info["name"] for block_info in blocks_info}
                blocks_to_remove = [block for block in collection if block.name in block_names]
                
                for block in blocks_to_remove:
                    try:
                        collection.remove(block)
                    except:
                        pass  # Some blocks might be in use and can't be removed
            
            # Append data blocks from the commit blend file
            with bpy.data.libraries.load(str(blend_filepath)) as (data_from, data_to):
                # Get all available data from the blend file
                data_to.objects = data_from.objects
                data_to.meshes = data_from.meshes
                data_to.materials = data_from.materials
                data_to.images = data_from.images
                data_to.texts = data_from.texts
                data_to.actions = data_from.actions
                data_to.node_groups = data_from.node_groups
            
            # Link objects to the current scene if they're not already linked
            for obj in data_to.objects:
                if obj and obj.name not in bpy.context.scene.collection.objects:
                    bpy.context.scene.collection.objects.link(obj)
            
            # Update current commit in metadata
            metadata["current_commit"] = self.commit_hash
            from .utils import save_commit_metadata
            save_commit_metadata(gitblend_dir, metadata)
            
            self.report({'INFO'}, f"Checked out commit: {commit_data.get('message', self.commit_hash)}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to checkout commit: {str(e)}")
            return {'CANCELLED'}


class GITBLEND_OT_ListCommits(bpy.types.Operator):
    """List all available commits."""
    bl_idname = "gitblend.list_commits"
    bl_label = "List Commits"
    bl_description = "List all available commits"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        try:
            gitblend_dir = get_gitblend_dir()
            if not gitblend_dir.exists():
                self.report({'ERROR'}, "Git Blend not initialized.")
                return {'CANCELLED'}
            
            metadata = load_commit_metadata(gitblend_dir)
            commits = metadata.get("commits", {})
            
            if not commits:
                self.report({'INFO'}, "No commits found")
                return {'FINISHED'}
            
            print("\n=== Git Blend Commits ===")
            for commit_hash, commit_data in commits.items():
                message = commit_data.get("message", "No message")
                timestamp = commit_data.get("timestamp", "Unknown time")
                current = " (current)" if commit_hash == metadata.get("current_commit") else ""
                print(f"{commit_hash[:8]}: {message} - {timestamp}{current}")
            
            self.report({'INFO'}, f"Found {len(commits)} commits (see console for details)")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to list commits: {str(e)}")
            return {'CANCELLED'}