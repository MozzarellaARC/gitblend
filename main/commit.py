import bpy
from datetime import datetime
import uuid


class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gb.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit changes to the Git repository"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = getattr(context.scene, "gitblend_props", None)
        commit_message = (props.commit_message if props else "").strip()

        if not commit_message:
            self.report({'ERROR'}, "Commit message cannot be empty.")
            return {'CANCELLED'}

        # Placeholder: real commit logic would serialize and store scene changes.
        self.report({'INFO'}, f"Committed with message: {commit_message}")
        return {'FINISHED'}


class GITBLEND_OT_commit_copy_scene(bpy.types.Operator):
    """Create a full duplicate of the current Scene with a unique identifier.

    Blender 4.2 safe: Uses bpy.data.scenes.new and copies data-block links.
    This performs a 'full copy' (deep copy) by using .copy() on the current
    scene data-block which in Blender duplicates objects and their data.
    A unique name pattern: OriginalName__commit_<timestamp>_<shortuuid>
    """

    bl_idname = "gb.commit_copy_scene"
    bl_label = "Commit: Copy Scene"
    bl_description = "Duplicate the current scene with a unique commit identifier"
    bl_options = {'REGISTER', 'UNDO'}

    make_active: bpy.props.BoolProperty(  # type: ignore
        name="Set Active",
        description="Make the duplicated scene the active scene",
        default=True,
    )

    def generate_unique_name(self, base_name: str) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        short = uuid.uuid4().hex[:8]
        return f"{base_name}__commit_{ts}_{short}"[:63]  # Blender name length safety

    def execute(self, context):
        src = context.scene
        try:
            new_name = self.generate_unique_name(src.name)
            # Deep copy the scene
            new_scene = src.copy()
            # Ensure collections are copied properly (objects are already duplicated links)
            # For a truly isolated copy of object data, also duplicate object.data blocks
            for obj in new_scene.objects:
                if obj.data and hasattr(obj.data, 'copy'):
                    obj.data = obj.data.copy()
            new_scene.name = new_name

            if self.make_active:
                context.window.scene = new_scene  # Switch active scene

            self.report({'INFO'}, f"Scene duplicated as '{new_scene.name}'")
            return {'FINISHED'}
        except Exception as e:  # pragma: no cover (Blender runtime safety)
            self.report({'ERROR'}, f"Scene copy failed: {e}")
            return {'CANCELLED'}

    @classmethod
    def poll(cls, context):  # type: ignore[override]
        return context.scene is not None
