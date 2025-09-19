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
            
            # Get parent commit hash (latest commit)
            parent_hash = None
            commits = metadata.get('commits', [])
            if commits:
                parent_hash = commits[-1]['hash']
            
            # Detect changes before generating commit
            changes_detected, change_summary = self._detect_changes(gitblend_dir, parent_hash)
            
            if not changes_detected:
                self.report({'INFO'}, "No changes detected - nothing to commit")
                return {'CANCELLED'}
            
            # Generate new commit data
            timestamp = datetime.now().isoformat()
            current_time = int(time.time())
            
            # Generate new commit hash
            new_commit_hash = self._generate_commit_hash(current_time, commit_message, parent_hash)
            
            # Export current data blocks to final .blend file
            final_blend_path = gitblend_dir / f"{new_commit_hash}.blend"
            self._export_data_blocks(str(final_blend_path))
            
            # Save signature file for this commit
            signature_file = gitblend_dir / f"{new_commit_hash}_signature.json"
            current_signature = self._generate_data_signature()
            with signature_file.open('w') as f:
                json.dump(current_signature, f, indent=2)
            
            # Clean up temporary signature file if it exists
            temp_signature_file = gitblend_dir / "temp_current_signature.json"
            if temp_signature_file.exists():
                temp_signature_file.unlink()
            
            # Create new commit metadata with change summary
            new_commit = {
                "hash": new_commit_hash,
                "timestamp": timestamp,
                "message": commit_message,
                "parent": parent_hash,
                "changes": change_summary
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
            
            # Report with change summary
            changes_text = ", ".join([f"{count} {type_name}" for type_name, count in change_summary.items() if count > 0])
            self.report({'INFO'}, f"Committed: {new_commit_hash[:8]} - {changes_text}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to commit: {str(e)}")
            return {'CANCELLED'}
    
    def _detect_changes(self, gitblend_dir, parent_hash):
        """Detect changes by comparing current data blocks with previous commit"""
        if not parent_hash:
            # First commit - everything is new
            current_counts = self._get_data_block_counts()
            change_summary = {
                "objects": current_counts.get("objects", 0),
                "meshes": current_counts.get("meshes", 0),
                "materials": current_counts.get("materials", 0),
                "images": current_counts.get("images", 0),
                "texts": current_counts.get("texts", 0),
                "actions": current_counts.get("actions", 0)
            }
            return True, change_summary
        
        # Load previous commit to compare
        previous_blend_path = gitblend_dir / f"{parent_hash}.blend"
        if not previous_blend_path.exists():
            # Previous commit file missing, assume changes
            current_counts = self._get_data_block_counts()
            change_summary = {type_name: count for type_name, count in current_counts.items()}
            return True, change_summary
        
        # Create current state signature
        current_signature = self._generate_data_signature()
        
        # Load previous signature if available
        previous_signature_file = gitblend_dir / f"{parent_hash}_signature.json"
        previous_signature = {}
        
        if previous_signature_file.exists():
            try:
                with previous_signature_file.open('r') as f:
                    previous_signature = json.load(f)
            except Exception:
                pass
        
        # Compare signatures to detect changes
        changes_detected, change_summary = self._compare_signatures(current_signature, previous_signature)
        
        if changes_detected:
            # Save current signature for future comparisons
            current_signature_file = gitblend_dir / f"temp_current_signature.json"
            with current_signature_file.open('w') as f:
                json.dump(current_signature, f, indent=2)
        
        return changes_detected, change_summary
    
    def _generate_data_signature(self):
        """Generate a signature of current data blocks for change detection"""
        signature = {
            "objects": {},
            "meshes": {},
            "materials": {},
            "images": {},
            "texts": {},
            "actions": {}
        }
        
        # Objects signature
        for obj in bpy.data.objects:
            obj_sig = {
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location) if hasattr(obj, 'location') else None,
                "rotation": list(obj.rotation_euler) if hasattr(obj, 'rotation_euler') else None,
                "scale": list(obj.scale) if hasattr(obj, 'scale') else None,
                "data_name": obj.data.name if obj.data else None
            }
            signature["objects"][obj.name] = obj_sig
        
        # Meshes signature
        for mesh in bpy.data.meshes:
            mesh_sig = {
                "name": mesh.name,
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "materials": [mat.name if mat else None for mat in mesh.materials]
            }
            signature["meshes"][mesh.name] = mesh_sig
        
        # Materials signature
        for mat in bpy.data.materials:
            mat_sig = {
                "name": mat.name,
                "use_nodes": mat.use_nodes,
                "diffuse_color": list(mat.diffuse_color) if hasattr(mat, 'diffuse_color') else None
            }
            signature["materials"][mat.name] = mat_sig
        
        # Images signature
        for img in bpy.data.images:
            img_sig = {
                "name": img.name,
                "size": list(img.size) if hasattr(img, 'size') else None,
                "filepath": img.filepath if hasattr(img, 'filepath') else None,
                "file_format": img.file_format if hasattr(img, 'file_format') else None
            }
            signature["images"][img.name] = img_sig
        
        # Texts signature
        for text in bpy.data.texts:
            text_sig = {
                "name": text.name,
                "lines_count": len(text.lines) if hasattr(text, 'lines') else 0,
                "content_hash": hashlib.md5(text.as_string().encode()).hexdigest() if hasattr(text, 'as_string') else None
            }
            signature["texts"][text.name] = text_sig
        
        # Actions signature
        for action in bpy.data.actions:
            action_sig = {
                "name": action.name,
                "frame_range": list(action.frame_range) if hasattr(action, 'frame_range') else None,
                "fcurves_count": len(action.fcurves) if hasattr(action, 'fcurves') else 0
            }
            signature["actions"][action.name] = action_sig
        
        return signature
    
    def _compare_signatures(self, current_sig, previous_sig):
        """Compare two data signatures and return changes detected"""
        changes = {}
        has_changes = False
        
        for data_type in ["objects", "meshes", "materials", "images", "texts", "actions"]:
            current_items = current_sig.get(data_type, {})
            previous_items = previous_sig.get(data_type, {})
            
            # Count additions and removals
            added = set(current_items.keys()) - set(previous_items.keys())
            removed = set(previous_items.keys()) - set(current_items.keys())
            common = set(current_items.keys()) & set(previous_items.keys())
            
            # Check for modifications in common items
            modified = 0
            for item_name in common:
                if current_items[item_name] != previous_items[item_name]:
                    modified += 1
            
            type_changes = len(added) + len(removed) + modified
            if type_changes > 0:
                has_changes = True
                changes[data_type] = {
                    "added": len(added),
                    "removed": len(removed),
                    "modified": modified,
                    "total": type_changes
                }
            else:
                changes[data_type] = {
                    "added": 0,
                    "removed": 0,
                    "modified": 0,
                    "total": 0
                }
        
        # Create summary for display
        change_summary = {}
        for data_type, stats in changes.items():
            if stats["total"] > 0:
                change_summary[data_type] = stats["total"]
        
        return has_changes, change_summary
    
    def _get_data_block_counts(self):
        """Get counts of current data blocks"""
        return {
            "objects": len(bpy.data.objects),
            "meshes": len(bpy.data.meshes),
            "materials": len(bpy.data.materials),
            "images": len(bpy.data.images),
            "texts": len(bpy.data.texts),
            "actions": len(bpy.data.actions)
        }
    
    def _get_previous_data_block_counts(self, previous_blend_path):
        """Get counts of data blocks from previous commit by temporarily loading it"""
        # This is a simplified approach - in practice, you might want to store
        # data block metadata in the commit information for better performance
        try:
            # For now, we'll estimate based on file size differences
            # A more sophisticated approach would involve loading the previous blend file
            # and analyzing its contents, but that's complex and slow
            
            # Return current counts as fallback (this ensures changes are detected)
            return self._get_data_block_counts()
            
        except Exception:
            # If we can't analyze previous commit, assume everything is new
            return {}
    
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

