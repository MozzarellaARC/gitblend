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


def _copy_object_from_stash(stashed_obj: bpy.types.Object, target_scene: bpy.types.Scene, original_name: str) -> bpy.types.Object:
    """Copy an object from stash back to target scene, resolving name conflicts."""
    # Create a copy of the stashed object
    new_obj = stashed_obj.copy()
    
    # Copy the object's data (mesh, etc.) if it exists
    if stashed_obj.data:
        new_obj.data = stashed_obj.data.copy()
    
    # Resolve name conflicts by finding a unique name
    base_name = original_name
    counter = 1
    final_name = base_name
    
    while final_name in [obj.name for obj in target_scene.objects]:
        final_name = f"{base_name}.{counter:03d}"
        counter += 1
    
    new_obj.name = final_name
    
    # Link the object to the target scene
    target_scene.collection.objects.link(new_obj)
    
    return new_obj


def _remove_stashed_objects(stash_entry, stash_scene: bpy.types.Scene):
    """Remove stashed objects from the stash scene."""
    stashed_names = stash_entry.stashed_names.split(", ")
    
    for stashed_name in stashed_names:
        stashed_name = stashed_name.strip()
        if stashed_name in stash_scene.objects:
            obj = stash_scene.objects[stashed_name]
            # Remove object data if it exists and has no other users
            if obj.data and obj.data.users == 1:
                bpy.data.meshes.remove(obj.data, do_unlink=True)
            # Remove the object itself
            bpy.data.objects.remove(obj, do_unlink=True)


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
        # Set stash operation flag to prevent auto-checkout interference
        wm = context.window_manager
        if wm.get('gitblend_stash_in_progress'):
            self.report({'WARNING'}, "Stash operation already in progress")
            return {'CANCELLED'}
        
        wm['gitblend_stash_in_progress'] = True
        
        try:
            selected_objects = context.selected_objects
            
            if not selected_objects:
                self.report({'WARNING'}, "No objects selected to stash")
                return {'CANCELLED'}
            
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
            
        finally:
            # Always clean up the stash flag
            if 'gitblend_stash_in_progress' in wm:
                del wm['gitblend_stash_in_progress']


class GITBLEND_OT_unstash(bpy.types.Operator):
    """Unstash objects from _stash scene back to current scene"""
    bl_idname = "gitblend.unstash"
    bl_label = "Unstash Objects"
    bl_description = "Copy stashed objects back to current scene with name resolution"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Check if the operator can be executed."""
        props = context.scene.gitblend_props
        return (props.stashed_objects and 
                props.stashed_objects_index >= 0 and 
                props.stashed_objects_index < len(props.stashed_objects))

    def execute(self, context):
        """Execute the unstash operation."""
        # Set stash operation flag to prevent auto-checkout interference
        wm = context.window_manager
        if wm.get('gitblend_stash_in_progress'):
            self.report({'WARNING'}, "Stash operation already in progress")
            return {'CANCELLED'}
        
        wm['gitblend_stash_in_progress'] = True
        
        try:
            props = context.scene.gitblend_props
            
            if not props.stashed_objects or props.stashed_objects_index < 0:
                self.report({'WARNING'}, "No stash selected")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to access stash properties: {e}")
            return {'CANCELLED'}
        
        try:
            # Get the selected stash entry
            stash_entry = props.stashed_objects[props.stashed_objects_index]
            
            # Check if _stash scene exists
            stash_scene_name = "_stash"
            if stash_scene_name not in bpy.data.scenes:
                self.report({'ERROR'}, "Stash scene not found")
                return {'CANCELLED'}
            
            stash_scene = bpy.data.scenes[stash_scene_name]
            current_scene = context.scene
            
            # Parse stashed object names and original names
            stashed_names = [name.strip() for name in stash_entry.stashed_names.split(", ")]
            original_names = [name.strip() for name in stash_entry.original_names.split(", ")]
            
            if len(stashed_names) != len(original_names):
                self.report({'ERROR'}, "Mismatch between stashed and original object counts")
                return {'CANCELLED'}
            
            # Copy objects back to current scene
            unstashed_objects = []
            for stashed_name, original_name in zip(stashed_names, original_names):
                if stashed_name not in stash_scene.objects:
                    self.report({'WARNING'}, f"Stashed object '{stashed_name}' not found in stash scene")
                    continue
                
                try:
                    stashed_obj = stash_scene.objects[stashed_name]
                    unstashed_obj = _copy_object_from_stash(stashed_obj, current_scene, original_name)
                    unstashed_objects.append(unstashed_obj)
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to unstash object '{stashed_name}': {e}")
                    continue
            
            if not unstashed_objects:
                self.report({'ERROR'}, "Failed to unstash any objects")
                return {'CANCELLED'}
            
            # Force UI redraw
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            
            object_count = len(unstashed_objects)
            self.report({'INFO'}, f"Unstashed {object_count} object(s) from UID: {stash_entry.uid[:8]}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to unstash objects: {e}")
            return {'CANCELLED'}
            
        finally:
            # Always clean up the stash flag
            if 'gitblend_stash_in_progress' in wm:
                del wm['gitblend_stash_in_progress']


class GITBLEND_OT_delete_stash(bpy.types.Operator):
    """Delete stash entry and remove stashed objects from _stash scene"""
    bl_idname = "gitblend.delete_stash"
    bl_label = "Delete Stash"
    bl_description = "Remove stash entry and delete stashed objects from _stash scene"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Check if the operator can be executed."""
        props = context.scene.gitblend_props
        return (props.stashed_objects and 
                props.stashed_objects_index >= 0 and 
                props.stashed_objects_index < len(props.stashed_objects))

    def execute(self, context):
        """Execute the delete stash operation."""
        # Set stash operation flag to prevent auto-checkout interference
        wm = context.window_manager
        if wm.get('gitblend_stash_in_progress'):
            self.report({'WARNING'}, "Stash operation already in progress")
            return {'CANCELLED'}
        
        wm['gitblend_stash_in_progress'] = True
        
        try:
            props = context.scene.gitblend_props
            
            if not props.stashed_objects or props.stashed_objects_index < 0:
                self.report({'WARNING'}, "No stash selected")
                return {'CANCELLED'}
            
            # Get the selected stash entry
            stash_index = props.stashed_objects_index
            stash_entry = props.stashed_objects[stash_index]
            stash_uid = stash_entry.uid[:8]
            
            # Check if _stash scene exists
            stash_scene_name = "_stash"
            if stash_scene_name in bpy.data.scenes:
                stash_scene = bpy.data.scenes[stash_scene_name]
                
                # Remove stashed objects from _stash scene
                try:
                    _remove_stashed_objects(stash_entry, stash_scene)
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to remove some stashed objects: {e}")
            
            # Remove the stash entry from the collection
            props.stashed_objects.remove(stash_index)
            
            # Adjust the active index
            if props.stashed_objects_index >= len(props.stashed_objects):
                props.stashed_objects_index = len(props.stashed_objects) - 1
            
            # Force UI redraw
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            
            self.report({'INFO'}, f"Deleted stash UID: {stash_uid}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to delete stash: {e}")
            return {'CANCELLED'}
            
        finally:
            # Always clean up the stash flag
            if 'gitblend_stash_in_progress' in wm:
                del wm['gitblend_stash_in_progress']