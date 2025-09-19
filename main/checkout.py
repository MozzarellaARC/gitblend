import bpy  # type: ignore
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Set


class GITBLEND_OT_Checkout(bpy.types.Operator):
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_description = "Checkout and restore scene to selected commit"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        # Show confirmation dialog
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if not bpy.data.filepath:
            self.report({'ERROR'}, "Please save the blend file first")
            return {'CANCELLED'}

        props = context.scene.gitblend_props
        
        # Check if any commit is selected
        if not props.commits or props.commits_index < 0 or props.commits_index >= len(props.commits):
            self.report({'ERROR'}, "No commit selected")
            return {'CANCELLED'}

        selected_commit = props.commits[props.commits_index]
        target_hash = selected_commit.hash

        if not target_hash:
            self.report({'ERROR'}, "Invalid commit hash")
            return {'CANCELLED'}

        try:
            # Restore scene to the selected commit
            self._restore_to_commit(target_hash)
            self.report({'INFO'}, f"Checked out to commit: {target_hash[:8]}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Checkout failed: {str(e)}")
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.gitblend_props
        
        if props.commits and 0 <= props.commits_index < len(props.commits):
            selected_commit = props.commits[props.commits_index]
            layout.label(text="This will replace the current scene with:")
            layout.label(text=f"Commit: {selected_commit.hash[:8]}")
            layout.label(text=f"Message: {selected_commit.message}")
            layout.separator()
            layout.label(text="Unsaved changes will be lost!", icon='ERROR')

    def _restore_to_commit(self, target_hash: str):
        """Restore the scene to the state of the specified commit"""
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        
        if not gitblend_dir.exists():
            raise Exception("Git Blend directory not found")

        # Load commit metadata
        metadata_file = gitblend_dir / "commits.json"
        if not metadata_file.exists():
            raise Exception("Commit metadata not found")

        with metadata_file.open('r') as f:
            metadata = json.load(f)

        commits = metadata.get('commits', [])
        target_commit = None
        
        # Find the target commit
        for commit in commits:
            if commit.get('hash', '') == target_hash:
                target_commit = commit
                break
        
        if not target_commit:
            raise Exception(f"Commit {target_hash} not found")

        # Use delta reconstruction approach
        self._reconstruct_from_deltas(commits, target_hash, gitblend_dir)

    def _reconstruct_from_deltas(self, commits: list, target_hash: str, gitblend_dir: Path):
        """Reconstruct scene state by applying deltas up to target commit"""
        
        # Build commit chain from initial to target
        commit_chain = self._build_commit_chain(commits, target_hash)
        
        # Start with clean scene
        self._clear_scene_data()
        
        # Apply each commit in order
        for commit_hash in commit_chain:
            self._apply_commit_delta(commit_hash, gitblend_dir)
        
        # Link objects to scene
        self._link_objects_to_scene()

    def _build_commit_chain(self, commits: list, target_hash: str) -> list:
        """Build a chain of commits from initial to target commit"""
        
        # Create commit lookup
        commit_lookup = {commit['hash']: commit for commit in commits}
        
        # Build chain by following parent relationships backwards
        chain = []
        current_hash = target_hash
        
        while current_hash:
            if current_hash not in commit_lookup:
                break
            
            chain.append(current_hash)
            commit = commit_lookup[current_hash]
            current_hash = commit.get('parent_hash')
        
        # Reverse to get chronological order (oldest first)
        return list(reversed(chain))

    def _apply_commit_delta(self, commit_hash: str, gitblend_dir: Path):
        """Apply the delta changes from a specific commit"""
        
        # Load the commit blend file
        commit_blend_file = gitblend_dir / f"{commit_hash}.blend"
        if not commit_blend_file.exists():
            # Skip missing commits (might be initial commit issue)
            return

        # Load only the data blocks that were changed in this commit
        self._load_commit_data_selective(commit_blend_file)

    def _load_commit_data_selective(self, commit_blend_path: Path):
        """Selectively load data blocks from commit, replacing existing ones"""
        
        # Data block types to handle (from data.instructions.md)
        data_block_types = [
            ('objects', bpy.data.objects),
            ('meshes', bpy.data.meshes), 
            ('materials', bpy.data.materials),
            ('images', bpy.data.images),
            ('texts', bpy.data.texts),
            ('actions', bpy.data.actions)
        ]
        
        # Load data blocks from commit file
        with bpy.data.libraries.load(str(commit_blend_path)) as (data_from, data_to):
            
            for block_type_name, target_collection in data_block_types:
                if hasattr(data_from, block_type_name):
                    source_collection = getattr(data_from, block_type_name)
                    target_attr = getattr(data_to, block_type_name)
                    
                    # Load all items from this collection
                    for item_name in source_collection:
                        # Remove existing item with same name if it exists
                        existing_item = target_collection.get(item_name)
                        if existing_item:
                            try:
                                target_collection.remove(existing_item)
                            except Exception:
                                pass
                        
                        # Load the new/updated item
                        target_attr.append(item_name)

    def _load_commit_data(self, commit_blend_path: Path):
        """Load data blocks from a commit blend file into the current scene (legacy method)"""
        
        # Clear existing data blocks (following data.instructions.md)
        self._clear_scene_data()
        
        # Load data blocks from the commit blend file
        data_block_types = ['objects', 'meshes', 'materials', 'images', 'texts', 'actions']
        
        with bpy.data.libraries.load(str(commit_blend_path)) as (data_from, data_to):
            # Load each data block type
            for block_type in data_block_types:
                if hasattr(data_from, block_type) and hasattr(data_to, block_type):
                    source_collection = getattr(data_from, block_type)
                    target_collection = getattr(data_to, block_type)
                    
                    # Load all items from this collection
                    for item_name in source_collection:
                        target_collection.append(item_name)

        # Link loaded objects to the scene
        self._link_objects_to_scene()

    def _clear_scene_data(self):
        """Clear existing scene data blocks to prepare for checkout"""
        
        # Remove all objects from scene and delete them
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        
        # Clear various data block collections
        data_collections = [
            ('meshes', bpy.data.meshes),
            ('materials', bpy.data.materials),
            ('images', bpy.data.images),
            ('texts', bpy.data.texts),
            ('actions', bpy.data.actions)
        ]
        
        for collection_name, collection in data_collections:
            # Remove all items from each collection
            items_to_remove = [item for item in collection]
            for item in items_to_remove:
                try:
                    collection.remove(item)
                except Exception:
                    # Some items might be protected or in use
                    pass

    def _link_objects_to_scene(self):
        """Link loaded objects to the current scene"""
        scene = bpy.context.scene
        
        # Link all loaded objects to the scene
        for obj in bpy.data.objects:
            # Only link if not already in scene
            if obj.name not in scene.objects:
                try:
                    scene.collection.objects.link(obj)
                except Exception:
                    # Object might already be linked or have issues
                    pass

def get_current_commit_hash(context) -> str:
    """Get the hash of the current commit state (utility function)"""
    # This would compare current scene state with latest commit
    # For now, return empty string to indicate "modified" state
    return ""


def is_scene_modified(context) -> bool:
    """Check if the current scene has uncommitted changes"""
    # This would compare current signatures with latest commit
    # For now, always return True to be safe
    return True

def register():
    bpy.utils.register_class(GITBLEND_OT_Checkout)


def unregister():
    bpy.utils.unregister_class(GITBLEND_OT_Checkout)