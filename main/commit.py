import bpy
import os
import json
import hashlib
import time
import filecmp
from datetime import datetime
from pathlib import Path


class GITBLEND_OT_Commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit current changes to git blend repository"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        # Can only commit if blend file is saved and gitblend is initialized
        if not bpy.data.filepath:
            return False
        
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        
        return gitblend_dir.exists()
    
    def execute(self, context):
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        metadata_file = gitblend_dir / "commits.json"
        
        # Validate .gitblend exists
        if not gitblend_dir.exists():
            self.report({'ERROR'}, "Git Blend not initialized. Run initialize first.")
            return {'CANCELLED'}
        
        try:
            # Load existing metadata
            metadata = {}
            if metadata_file.exists():
                with metadata_file.open('r') as f:
                    metadata = json.load(f)
            
            # Get commit message from UI
            props = context.scene.gitblend_props
            commit_message = props.commit_message.strip()
            
            if not commit_message:
                self.report({'ERROR'}, "Commit message is required")
                return {'CANCELLED'}
            
            # Generate new commit data
            timestamp = datetime.now().isoformat()
            current_time = int(time.time())
            
            # Get parent commit hash (latest commit)
            parent_hash = None
            commits = metadata.get('commits', [])
            if commits:
                parent_hash = commits[-1]['hash']
            
            # Generate new commit hash
            new_commit_hash = self._generate_commit_hash(current_time, commit_message, parent_hash)
            
            # Export current data blocks to temporary .blend file
            temp_blend_path = gitblend_dir / f"temp_{new_commit_hash}.blend"
            self._export_data_blocks(str(temp_blend_path))
            
            # Check if there are changes compared to the previous commit
            has_changes = True
            if parent_hash:
                previous_blend_path = gitblend_dir / f"{parent_hash}.blend"
                if previous_blend_path.exists():
                    has_changes = not filecmp.cmp(str(temp_blend_path), str(previous_blend_path), shallow=False)
            
            if not has_changes:
                # No changes detected, remove temp file and abort
                temp_blend_path.unlink()
                self.report({'INFO'}, "No changes detected")
                return {'CANCELLED'}
            
            # Move temp file to final location
            final_blend_path = gitblend_dir / f"{new_commit_hash}.blend"
            temp_blend_path.rename(final_blend_path)
            
            # Create new commit metadata
            new_commit = {
                "hash": new_commit_hash,
                "timestamp": timestamp,
                "message": commit_message,
                "parent": parent_hash
            }
            
            # Update metadata
            if 'commits' not in metadata:
                metadata['commits'] = []
            if 'version' not in metadata:
                metadata['version'] = 1
            
            metadata['commits'].append(new_commit)
            
            # Save updated metadata
            with metadata_file.open('w') as f:
                json.dump(metadata, f, indent=2)
            
            # Clear commit message
            props.commit_message = ""
            
            # Ensure initialized property is set to True
            props.initialized = True
            
            # Refresh UI
            from .initialize import populate_ui_from_metadata
            populate_ui_from_metadata(context)
            
            self.report({'INFO'}, f"Committed: {new_commit_hash[:8]} - {commit_message}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to commit: {str(e)}")
            return {'CANCELLED'}
    
    def _generate_commit_hash(self, timestamp, message, parent_hash):
        """Generate SHA-256 hash for commit"""
        content = f"{timestamp}_{message}_{parent_hash or ''}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _export_data_blocks(self, export_path):
        """Export specified data blocks using bpy.data.libraries.write"""
        # Data blocks to export as specified in data.instructions.md
        data_blocks = {
            'objects': bpy.data.objects,
            'meshes': bpy.data.meshes,
            'materials': bpy.data.materials,
            'images': bpy.data.images,
            'texts': bpy.data.texts,
            'actions': bpy.data.actions
        }
        
        # Collect all data blocks to write
        data_blocks_to_write = set()
        
        for block_type, collection in data_blocks.items():
            for item in collection:
                data_blocks_to_write.add(item)
        
        # Write to .blend file
        bpy.data.libraries.write(export_path, data_blocks_to_write, fake_user=True)


def register_commit():
    bpy.utils.register_class(GITBLEND_OT_Commit)


def unregister_commit():
    bpy.utils.unregister_class(GITBLEND_OT_Commit)

