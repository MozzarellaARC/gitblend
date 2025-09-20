import bpy
import time
from .utils import (
    get_blend_file_hash,
    generate_commit_hash,
    get_gitblend_dir,
    export_data_blocks_to_blend,
    serialize_data_blocks,
    load_commit_metadata,
    save_commit_metadata
)
from .diff import get_changes


class GITBLEND_OT_Commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit current changes to git blend repository"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            # Get commit message from scene properties
            commit_message = context.scene.gitblend.commit_message if hasattr(context.scene, 'gitblend') else "Update blend file"
            
            # Check if git_blend is initialized
            gitblend_dir = get_gitblend_dir()
            if not gitblend_dir.exists():
                self.report({'ERROR'}, "Git Blend not initialized. Please initialize first.")
                return {'CANCELLED'}
            
            # Get changes
            changes = get_changes()
            if "error" in changes:
                self.report({'ERROR'}, f"Error getting changes: {changes['error']}")
                return {'CANCELLED'}
            
            # Check if there are any changes
            has_changes = any(
                any(change_list) for category_changes in changes.values() 
                for change_list in category_changes.values()
            )
            
            if not has_changes:
                self.report({'INFO'}, "No changes detected")
                return {'CANCELLED'}
            
            # Load existing metadata
            metadata = load_commit_metadata(gitblend_dir)
            
            # Generate new commit hash based on timestamp, message, and changes
            commit_timestamp = time.time()
            new_hash = generate_commit_hash(commit_message, commit_timestamp, changes)
            
            # Collect only modified/added data blocks for delta export
            delta_data_blocks = []
            data_blocks_dict = {
                "objects": [],
                "meshes": [],
                "materials": [],
                "images": [],
                "texts": [],
                "actions": [],
                "node_groups": []
            }
            
            # Collect changed data blocks
            for category, category_changes in changes.items():
                added_names = set(category_changes.get("added", []))
                modified_names = set(category_changes.get("modified", []))
                changed_names = added_names.union(modified_names)
                
                if changed_names:
                    if category == "objects":
                        blocks = [obj for obj in bpy.data.objects if obj.name in changed_names]
                    elif category == "meshes":
                        blocks = [mesh for mesh in bpy.data.meshes if mesh.name in changed_names]
                    elif category == "materials":
                        blocks = [mat for mat in bpy.data.materials if mat.name in changed_names]
                    elif category == "images":
                        blocks = [img for img in bpy.data.images if img.name in changed_names]
                    elif category == "texts":
                        blocks = [txt for txt in bpy.data.texts if txt.name in changed_names]
                    elif category == "actions":
                        blocks = [act for act in bpy.data.actions if act.name in changed_names]
                    elif category == "node_groups":
                        blocks = [ng for ng in bpy.data.node_groups if ng.name in changed_names]
                    else:
                        blocks = []
                    
                    data_blocks_dict[category] = blocks
                    delta_data_blocks.extend(blocks)
            
            # Export delta data blocks if there are any
            blend_filepath = None
            if delta_data_blocks:
                blend_filepath = export_data_blocks_to_blend(gitblend_dir, new_hash, delta_data_blocks)
                self.report({'INFO'}, f"Exported {len(delta_data_blocks)} changed data blocks")
            else:
                self.report({'INFO'}, "No data blocks to export (changes detected but no exportable blocks)")
                # Still continue to update metadata even if no blend file is created
            
            # For subsequent commits, merge with previous data
            if metadata.get("commits"):
                current_commit = metadata.get("current_commit")
                if current_commit and current_commit in metadata["commits"]:
                    previous_data = metadata["commits"][current_commit]["data_blocks"]
                    
                    # Merge previous data with new changes
                    for category in data_blocks_dict:
                        if category in previous_data:
                            # Keep previous data for unchanged items
                            previous_items = {item["name"]: item for item in previous_data[category]}
                            current_items = {block.name: block for block in data_blocks_dict[category]}
                            
                            # Add unchanged items from previous commit
                            for name, item_data in previous_items.items():
                                if name not in current_items:
                                    # Check if this item was removed
                                    if name not in changes[category].get("removed", []):
                                        # Add to current serialization (keeping previous data)
                                        pass  # We'll serialize current state below
            
            # Serialize all current data blocks (not just delta)
            all_current_data = {
                "objects": list(bpy.data.objects),
                "meshes": list(bpy.data.meshes),
                "materials": list(bpy.data.materials),
                "images": list(bpy.data.images),
                "texts": list(bpy.data.texts),
                "actions": list(bpy.data.actions),
                "node_groups": list(bpy.data.node_groups)
            }
            serialized_data = serialize_data_blocks(all_current_data)
            
            # Create commit entry
            commit_data = {
                "data_blocks": serialized_data,
                "blend_file": f"{new_hash}.blend" if blend_filepath else None,
                "timestamp": commit_timestamp,
                "message": commit_message,
                "changes": changes
            }
            
            # Update metadata
            metadata["commits"][new_hash] = commit_data
            metadata["current_commit"] = new_hash
            
            # Save metadata
            save_commit_metadata(gitblend_dir, metadata)
            
            # Refresh the commit list to show the new commit
            bpy.ops.gitblend.refresh_commits()

            self.report({'INFO'}, f"Committed changes: {commit_message}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to commit changes: {str(e)}")
            return {'CANCELLED'}
