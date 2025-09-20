import bpy  # type: ignore
import json
from pathlib import Path
from typing import Dict, List, Any, Set
from .utils import (
    get_gitblend_dir,
    load_commit_metadata,
    save_commit_metadata
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
            
            # Step 1: Read the JSON file in the .gitblend directory
            commit_json_data = self.read_commit_json(gitblend_dir)
            if not commit_json_data:
                self.report({'ERROR'}, "Failed to read commit data")
                return {'CANCELLED'}
            
            if self.commit_hash not in commit_json_data.get("commits", {}):
                self.report({'ERROR'}, f"Commit {self.commit_hash} not found")
                return {'CANCELLED'}
            
            commit_data = commit_json_data["commits"][self.commit_hash]
            
            # Step 2: Reconstruct the delta data blocks in the current .blend file
            success = self.reconstruct_delta_data_blocks(gitblend_dir, commit_data)
            if not success:
                self.report({'ERROR'}, "Failed to reconstruct delta data blocks")
                return {'CANCELLED'}
            
            # Step 3: If delta reconstruction is successful, proceed to import
            success = self.import_data_blocks_from_gitblend(gitblend_dir, commit_data)
            if not success:
                self.report({'ERROR'}, "Failed to import data blocks")
                return {'CANCELLED'}
            
            # Update current commit in metadata
            commit_json_data["current_commit"] = self.commit_hash
            save_commit_metadata(gitblend_dir, commit_json_data)
            
            self.report({'INFO'}, f"Checked out commit: {commit_data.get('message', self.commit_hash)}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to checkout commit: {str(e)}")
            return {'CANCELLED'}
    
    def read_commit_json(self, gitblend_dir: Path) -> Dict[str, Any]:
        """Read the JSON file in the .gitblend directory."""
        try:
            metadata = load_commit_metadata(gitblend_dir)
            return metadata
        except Exception as e:
            print(f"Error reading commit JSON: {e}")
            return {}
    
    def reconstruct_delta_data_blocks(self, gitblend_dir: Path, commit_data: Dict[str, Any]) -> bool:
        """Reconstruct the delta data blocks using selective replacement approach."""
        try:
            target_data_blocks = commit_data.get("data_blocks", {})
            
            # Alternative 1: Selective Delta Reconstruction
            success = self.selective_delta_reconstruction(gitblend_dir, commit_data, target_data_blocks)
            if success:
                return True
            
            # Alternative 2: Fresh Scene Approach (fallback)
            print("Selective reconstruction failed, trying fresh scene approach...")
            return self.fresh_scene_reconstruction(gitblend_dir, commit_data, target_data_blocks)
            
        except Exception as e:
            print(f"Error in reconstruct_delta_data_blocks: {e}")
            return False
    
    def selective_delta_reconstruction(self, gitblend_dir: Path, commit_data: Dict[str, Any], target_data_blocks: Dict[str, Any]) -> bool:
        """Selectively remove/add only the data blocks that differ from target state."""
        try:
            # Get current state
            current_state = self.get_current_data_block_state()
            
            # Compare and identify differences
            to_remove, to_add = self.compare_data_block_states(current_state, target_data_blocks)
            
            # Remove data blocks that shouldn't exist
            self.remove_specific_data_blocks(to_remove)
            
            # Validate blend file exists
            blend_file_hash = commit_data.get("blend_file_hash")
            blend_file = commit_data.get("blend_file")
            
            if blend_file_hash:
                blend_filepath = gitblend_dir / f"{blend_file_hash}.blend"
            elif blend_file:
                blend_filepath = gitblend_dir / blend_file
            else:
                print("No blend file information found")
                return False
            
            if not blend_filepath.exists():
                print(f"Blend file not found: {blend_filepath}")
                return False
            
            # Add data blocks that should exist
            success = self.add_specific_data_blocks(str(blend_filepath), to_add)
            
            print(f"Selective reconstruction: removed {sum(len(v) for v in to_remove.values())} items, added {sum(len(v) for v in to_add.values())} items")
            return success
            
        except Exception as e:
            print(f"Error in selective_delta_reconstruction: {e}")
            return False
    
    def fresh_scene_reconstruction(self, gitblend_dir: Path, commit_data: Dict[str, Any], target_data_blocks: Dict[str, Any]) -> bool:
        """Create a fresh scene and import all data blocks into it."""
        try:
            # Create a new scene
            checkout_scene_name = f"GitBlend_Checkout_{self.commit_hash[:8]}"
            
            # Remove existing checkout scene if it exists
            if checkout_scene_name in bpy.data.scenes:
                bpy.data.scenes.remove(bpy.data.scenes[checkout_scene_name])
            
            # Create new scene
            new_scene = bpy.data.scenes.new(checkout_scene_name)
            
            # Set as active scene
            bpy.context.window.scene = new_scene
            
            # Import all data blocks into the fresh scene
            blend_file_hash = commit_data.get("blend_file_hash")
            blend_file = commit_data.get("blend_file")
            
            if blend_file_hash:
                blend_filepath = gitblend_dir / f"{blend_file_hash}.blend"
            elif blend_file:
                blend_filepath = gitblend_dir / blend_file
            else:
                return False
            
            if not blend_filepath.exists():
                return False
            
            # Import all target data blocks
            success = self.import_all_data_blocks(str(blend_filepath), target_data_blocks)
            
            print(f"Fresh scene reconstruction completed in scene: {checkout_scene_name}")
            return success
            
        except Exception as e:
            print(f"Error in fresh_scene_reconstruction: {e}")
            return False
    
    def recursive_purge_all_data_blocks(self):
        """Make sure to recursive purge when deleting data blocks."""
        try:
            # First, clear all object selections and deselect everything
            bpy.ops.object.select_all(action='DESELECT')
            
            # Clear objects from all scenes and collections first
            for scene in bpy.data.scenes:
                # Clear all objects from scene
                scene.objects.clear()
                
                # Clear all collections in the scene
                for collection in scene.collection.children[:]:
                    scene.collection.children.unlink(collection)
            
            # Clear all collections
            for collection in list(bpy.data.collections):
                # Clear objects from collection
                collection.objects.clear()
                # Clear child collections
                for child in collection.children[:]:
                    collection.children.unlink(child)
            
            # Remove fake users and clear references
            for obj in list(bpy.data.objects):
                obj.use_fake_user = False
                # Clear all object data references
                if obj.data:
                    obj.data = None
                # Clear material slots
                obj.data = None
                for slot in obj.material_slots:
                    slot.material = None
            
            # Define data collections to purge in dependency order (reverse of import order)
            data_collections_info = [
                ("objects", bpy.data.objects),
                ("meshes", bpy.data.meshes),
                ("materials", bpy.data.materials),
                ("images", bpy.data.images),
                ("node_groups", bpy.data.node_groups),
                ("texts", bpy.data.texts),
                ("actions", bpy.data.actions),
                ("collections", bpy.data.collections)
            ]
            
            # Remove fake users first
            for name, collection in data_collections_info:
                for item in list(collection):
                    if hasattr(item, 'use_fake_user'):
                        item.use_fake_user = False
            
            # Multiple passes to ensure complete removal
            max_passes = 5
            for pass_num in range(max_passes):
                items_removed = 0
                
                for name, collection in data_collections_info:
                    items_before = len(collection)
                    
                    # Try to remove all items in the collection
                    for item in list(collection):
                        try:
                            collection.remove(item, do_unlink=True)
                            items_removed += 1
                        except Exception as e:
                            # If removal fails, try to clear fake user and references
                            if hasattr(item, 'use_fake_user'):
                                item.use_fake_user = False
                            if hasattr(item, 'user_clear'):
                                item.user_clear()
                    
                    items_after = len(collection)
                    if items_before > items_after:
                        print(f"Pass {pass_num + 1}: Removed {items_before - items_after} {name}")
                
                # If no items were removed in this pass, we're done
                if items_removed == 0:
                    break
            
            # Final purge of orphaned data blocks (multiple times for thoroughness)
            for _ in range(3):
                try:
                    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
                except Exception as e:
                    print(f"Warning during orphan purge: {e}")
            
            print("Recursive purge completed")
            
        except Exception as e:
            print(f"Error in recursive_purge_all_data_blocks: {e}")
    
    def import_data_blocks_from_gitblend(self, gitblend_dir: Path, commit_data: Dict[str, Any]) -> bool:
        """Utilize bpy.ops.wm.append to import data blocks from the .gitblend directory."""
        # This method is now handled by the reconstruction methods
        # Just return True since reconstruction already handles importing
        return True
    
    def get_current_data_block_state(self) -> Dict[str, List[str]]:
        """Get the current state of all data blocks in the scene."""
        current_state = {
            "objects": [obj.name for obj in bpy.data.objects],
            "meshes": [mesh.name for mesh in bpy.data.meshes],
            "materials": [mat.name for mat in bpy.data.materials],
            "images": [img.name for img in bpy.data.images],
            "texts": [text.name for text in bpy.data.texts],
            "actions": [action.name for action in bpy.data.actions],
            "node_groups": [ng.name for ng in bpy.data.node_groups]
        }
        return current_state
    
    def compare_data_block_states(self, current_state: Dict[str, List[str]], target_state: Dict[str, Any]) -> tuple:
        """Compare current and target states to identify what to remove and add."""
        to_remove = {}
        to_add = {}
        
        for category in current_state.keys():
            current_names = set(current_state[category])
            target_items = target_state.get(category, [])
            target_names = set(item.get("name", "") for item in target_items if item.get("name"))
            
            # Items to remove (exist in current but not in target)
            remove_names = current_names - target_names
            to_remove[category] = list(remove_names)
            
            # Items to add (exist in target but not in current)
            add_names = target_names - current_names
            to_add[category] = [item for item in target_items if item.get("name") in add_names]
        
        return to_remove, to_add
    
    def remove_specific_data_blocks(self, to_remove: Dict[str, List[str]]):
        """Remove specific data blocks by name."""
        try:
            # Remove in dependency order
            removal_order = [
                ("objects", bpy.data.objects),
                ("meshes", bpy.data.meshes),
                ("materials", bpy.data.materials),
                ("images", bpy.data.images),
                ("texts", bpy.data.texts),
                ("actions", bpy.data.actions),
                ("node_groups", bpy.data.node_groups)
            ]
            
            for category, collection in removal_order:
                names_to_remove = to_remove.get(category, [])
                for name in names_to_remove:
                    if name in collection:
                        try:
                            # First remove from scenes if it's an object
                            if category == "objects":
                                obj = collection[name]
                                for scene in bpy.data.scenes:
                                    if obj.name in scene.objects:
                                        scene.objects.unlink(obj)
                            
                            # Remove fake user if exists
                            item = collection[name]
                            if hasattr(item, 'use_fake_user'):
                                item.use_fake_user = False
                            
                            # Remove the data block
                            collection.remove(item)
                            print(f"Removed {category}: {name}")
                            
                        except Exception as e:
                            print(f"Warning: Could not remove {category} '{name}': {e}")
            
        except Exception as e:
            print(f"Error removing specific data blocks: {e}")
    
    def add_specific_data_blocks(self, blend_filepath: str, to_add: Dict[str, List[Dict]]) -> bool:
        """Add specific data blocks from the blend file."""
        try:
            # Import in dependency order
            import_order = [
                ("Image", "images"),
                ("NodeTree", "node_groups"),
                ("Material", "materials"),
                ("Mesh", "meshes"),
                ("Text", "texts"),
                ("Action", "actions"),
                ("Object", "objects")
            ]
            
            for blender_type, category in import_order:
                items_to_add = to_add.get(category, [])
                for item_info in items_to_add:
                    item_name = item_info.get("name", "")
                    if not item_name:
                        continue
                    
                    try:
                        directory = f"{blend_filepath}/{blender_type}/"
                        filepath = f"{directory}{item_name}"
                        
                        bpy.ops.wm.append(
                            filepath=filepath,
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
                        print(f"Added {blender_type}: {item_name}")
                        
                    except Exception as e:
                        print(f"Warning: Could not add {blender_type} '{item_name}': {e}")
            
            return True
            
        except Exception as e:
            print(f"Error adding specific data blocks: {e}")
            return False
    
    def import_all_data_blocks(self, blend_filepath: str, target_data_blocks: Dict[str, Any]) -> bool:
        """Import all data blocks into the fresh scene."""
        try:
            import_order = [
                ("Image", "images"),
                ("NodeTree", "node_groups"),
                ("Material", "materials"),
                ("Mesh", "meshes"),
                ("Text", "texts"),
                ("Action", "actions"),
                ("Object", "objects")
            ]
            
            for blender_type, category in import_order:
                data_list = target_data_blocks.get(category, [])
                for item_info in data_list:
                    item_name = item_info.get("name", "")
                    if not item_name:
                        continue
                    
                    try:
                        directory = f"{blend_filepath}/{blender_type}/"
                        filepath = f"{directory}{item_name}"
                        
                        bpy.ops.wm.append(
                            filepath=filepath,
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
                        print(f"Warning: Could not import {blender_type} '{item_name}': {e}")
            
            return True
            
        except Exception as e:
            print(f"Error importing all data blocks: {e}")
            return False