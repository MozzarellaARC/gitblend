import bpy
import hashlib
import time
from typing import Set, List


def _generate_uid() -> str:
    """Generate a unique identifier using sha-256 hash of current timestamp."""
    timestamp = str(time.time_ns())
    return hashlib.sha256(timestamp.encode()).hexdigest()[:8]


def _get_or_create_stash_scene() -> bpy.types.Scene:
    """Get the _stash scene, creating it if it doesn't exist."""
    stash_scene_name = "_stash"
    
    # Check if _stash scene already exists
    if stash_scene_name in bpy.data.scenes:
        return bpy.data.scenes[stash_scene_name]
    
    # Create new _stash scene
    stash_scene = bpy.data.scenes.new(stash_scene_name)
    return stash_scene


def _copy_object_to_scene(obj: bpy.types.Object, target_scene: bpy.types.Scene, uid_suffix: str) -> bpy.types.Object:
    """Copy an object to the target scene with UID suffix."""
    # Create a copy of the object
    new_obj = obj.copy()
    
    # Copy the object's data (mesh, etc.) if it exists
    if obj.data:
        new_obj.data = obj.data.copy()
    
    # Add UID suffix to the name
    new_obj.name = f"{obj.name}_{uid_suffix}"
    
    # Link the object to the target scene
    target_scene.collection.objects.link(new_obj)
    
    return new_obj


class GITBLEND_OT_stash(bpy.types.Operator):
    """Stash selected objects to _stash scene with UID suffix"""
    bl_idname = "gitblend.stash"
    bl_label = "Stash Selected Objects"
    bl_description = "Copy selected objects to _stash scene with unique ID suffix"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Check if the operator can be executed."""
        return context.selected_objects and len(context.selected_objects) > 0

    def execute(self, context):
        """Execute the stash operation."""
        selected_objects = context.selected_objects
        
        if not selected_objects:
            self.report({'WARNING'}, "No objects selected to stash")
            return {'CANCELLED'}
        
        try:
            # Get or create the _stash scene
            stash_scene = _get_or_create_stash_scene()
            
            # Generate a unique ID for this stash operation
            uid = _generate_uid()
            
            # Copy each selected object to the stash scene
            stashed_objects = []
            for obj in selected_objects:
                try:
                    stashed_obj = _copy_object_to_scene(obj, stash_scene, uid)
                    stashed_objects.append(stashed_obj)
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to stash object '{obj.name}': {e}")
                    continue
            
            if not stashed_objects:
                self.report({'ERROR'}, "Failed to stash any objects")
                return {'CANCELLED'}
            
            # Update the stash properties
            props = context.scene.gitblend_props
            stash_entry = props.stashed_objects.add()
            stash_entry.uid = uid
            stash_entry.original_names = ", ".join([obj.name for obj in selected_objects])
            stash_entry.stashed_names = ", ".join([obj.name for obj in stashed_objects])
            stash_entry.timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Update the active index
            props.stashed_objects_index = len(props.stashed_objects) - 1
            
            # Force UI redraw
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            
            object_count = len(stashed_objects)
            self.report({'INFO'}, f"Stashed {object_count} object(s) with UID: {uid}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to stash objects: {e}")
            return {'CANCELLED'}