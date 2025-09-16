import bpy
import hashlib
import time
from pathlib import Path
from typing import Any, Dict

# Use shared initialization + metadata utilities
from .initialize import ensure_gitblend_dir, append_commit, is_gitblend_initialized, is_ui_synced_with_metadata

"""
COMMIT ARCHITECTURE - OPERATION ORDER

The commit system follows a specific operation order to ensure data integrity and consistency:

1. VALIDATION PHASE:
   - Check if blend file is saved (must have filepath)
   - Verify .gitblend directory is initialized
   - Ensure UI is synchronized with metadata
   - Validate commit message is not empty

2. HASH GENERATION:
   - Compute SHA-256 hash from current scene state
   - Uses object names, types, and current timestamp for uniqueness
   - Hash serves as both filename and unique identifier

3. DATA COLLECTION PHASE:
   - Gather current scene and all its dependencies using bpy.data.libraries.write()
   - Collect objects, meshes, materials, textures, collections
   - Include world data, cameras, and modifier dependencies
   - Build a comprehensive set of data blocks for the snapshot

4. SNAPSHOT CREATION:
   - Write collected data blocks to .gitblend/{hash}.blend using bpy.data.libraries.write()
   - This creates a focused snapshot containing only scene-relevant data
   - More efficient than saving entire file (no unused data blocks)

5. METADATA UPDATE:
   - Add commit entry to in-memory UI list (props.commits)
   - Update active commit index to newly created commit
   - Persist commit metadata to .gitblend/metadata.json

6. UI REFRESH:
   - Force redraw of VIEW_3D areas to show updated commit list
   - Provide user feedback with success/error messages

CHECKOUT COMPATIBILITY:
- Commits created with bpy.data.libraries.write() are perfectly compatible with checkout
- Checkout uses bpy.data.libraries.load() to read the same data blocks
- This creates a consistent write/read cycle for scene data

BENEFITS OF THIS ARCHITECTURE:
- Selective data writing (smaller snapshots)
- Fast commit/checkout operations
- No interference with current working file
- Comprehensive dependency tracking
- Robust error handling at each phase
"""


def _compute_scene_hash(scene: bpy.types.Scene) -> str:
    """Compute a sha-256 hash representing the current scene state.
    For now we use a combination of object names, modification times and a timestamp
    to ensure uniqueness. This can evolve into a deterministic content hash later.
    """
    h = hashlib.sha256()
    # Basic entropy: object names and counts
    try:
        for obj in scene.objects:
            h.update(obj.name.encode('utf-8', 'ignore'))
            h.update(str(obj.type).encode())
    except Exception:
        pass
    # Add current time to guarantee uniqueness even if scene unchanged
    h.update(str(time.time_ns()).encode())
    return h.hexdigest()


class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit changes to the Git repository"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):  # type: ignore
        # Must have saved blend file and initialization present
        blend_path = bpy.data.filepath
        if not blend_path:
            return False
        try:
            from pathlib import Path as _P
            project_dir = _P(blend_path).resolve().parent
            if not is_gitblend_initialized(project_dir):
                return False
            # Must also be synced with metadata
            return is_ui_synced_with_metadata(context)
        except Exception:
            return False

    def execute(self, context):
        # Set commit operation flag to prevent auto-checkout interference
        wm = context.window_manager
        if wm.get('gitblend_commit_in_progress'):
            self.report({'WARNING'}, "Commit operation already in progress")
            return {'CANCELLED'}
        
        wm['gitblend_commit_in_progress'] = True
        
        try:
            props = getattr(context.scene, "gitblend_props", None)
            commit_message = (props.commit_message if props else "").strip()

            if not commit_message:
                self.report({'ERROR'}, "Commit message cannot be empty.")
                return {'CANCELLED'}
            
            # Determine current working .blend file path
            current_filepath = bpy.data.filepath
            if not current_filepath:
                self.report({'ERROR'}, "Please save the .blend file before committing.")
                return {'CANCELLED'}

            current_dir = Path(current_filepath).resolve().parent
            
            # Check if .gitblend is initialized
            if not is_gitblend_initialized(current_dir):
                self.report({'ERROR'}, "Repository not initialized. Please initialize first.")
                return {'CANCELLED'}
            
            # Check if UI is synced with metadata
            if not is_ui_synced_with_metadata(context):
                self.report({'ERROR'}, "Commit history not synchronized. Please sync first.")
                return {'CANCELLED'}
            try:
                gitblend_dir = ensure_gitblend_dir(current_dir)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to create .gitblend directory: {e}")
                return {'CANCELLED'}

            # Compute a unique sha-256 filename
            scene_hash = _compute_scene_hash(context.scene)
            snapshot_path = gitblend_dir / f"{scene_hash}.blend"

            # Save snapshot using bpy.data.libraries.write() for better control
            try:
                # Collect all data to write to the snapshot
                # We want to include the current scene and all its dependencies
                current_scene = context.scene
                
                # Gather all data blocks that need to be saved
                data_blocks = set()
                
                # Add the current scene
                data_blocks.add(current_scene)
                
                # Add all objects in the scene and their dependencies
                for obj in current_scene.objects:
                    data_blocks.add(obj)
                    # Add object data (mesh, curve, etc.)
                    if obj.data:
                        data_blocks.add(obj.data)
                    # Add materials
                    if hasattr(obj.data, 'materials') and obj.data.materials:
                        for material in obj.data.materials:
                            if material:
                                data_blocks.add(material)
                                # Add material nodes and textures
                                if material.use_nodes and material.node_tree:
                                    data_blocks.add(material.node_tree)
                                    for node in material.node_tree.nodes:
                                        if node.type == 'TEX_IMAGE' and node.image:
                                            data_blocks.add(node.image)
                    # Add modifiers data if any
                    for modifier in obj.modifiers:
                        if hasattr(modifier, 'object') and modifier.object:
                            data_blocks.add(modifier.object)
                
                # Add collections used in the scene
                for collection in current_scene.collection.children_recursive:
                    data_blocks.add(collection)
                if current_scene.collection:
                    data_blocks.add(current_scene.collection)
                
                # Add world data
                if current_scene.world:
                    data_blocks.add(current_scene.world)
                    if current_scene.world.use_nodes and current_scene.world.node_tree:
                        data_blocks.add(current_scene.world.node_tree)
                
                # Add camera and other scene-linked objects
                if current_scene.camera:
                    data_blocks.add(current_scene.camera)
                    if current_scene.camera.data:
                        data_blocks.add(current_scene.camera.data)
                
                # Write the data blocks to the snapshot file
                # bpy.data.libraries.write() expects a set, not a list
                bpy.data.libraries.write(str(snapshot_path), data_blocks, fake_user=False)
                
            except Exception as e:
                self.report({'ERROR'}, f"Failed to write snapshot using bpy.data.libraries.write(): {e}")
                return {'CANCELLED'}

            # Record commit in in-memory history (UI list)
            timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S')
            if props:
                entry = props.commits.add()
                entry.hash = scene_hash
                entry.message = commit_message
                entry.timestamp = timestamp_str
                props.commits_index = len(props.commits) - 1
                # Preserve last commit message (user request): do not clear commit_message
            # Persist commit metadata
            try:
                append_commit(current_dir, {
                    "hash": scene_hash,
                    "message": commit_message,
                    "timestamp": timestamp_str,
                    "snapshot": snapshot_path.name,
                })
            except Exception as e:
                self.report({'WARNING'}, f"Metadata write failed: {e}")
            # Force UI redraw
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

            self.report({'INFO'}, f"Committed snapshot {snapshot_path.name} : {commit_message}")
            return {'FINISHED'}
        
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error during commit: {e}")
            return {'CANCELLED'}
        
        finally:
            # Always clean up the commit flag
            if 'gitblend_commit_in_progress' in wm:
                del wm['gitblend_commit_in_progress']