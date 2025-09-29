import bpy
from pathlib import Path
from bpy.app.handlers import persistent

@persistent
def stage_obj_handler(self, context):
    # Ensure save
    if not bpy.data.filepath:
        return {'CANCELLED'}
    
    # Only stage if .gitblend directory already exists
    gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
    if not gitblend_dir.exists():
        return {'CANCELLED'}

    staging_dir = gitblend_dir / "staging"
    staging_dir.mkdir(exist_ok=True)
    
    def should_ignore(obj: bpy.types.Object) -> bool:
        """Return True if the object belongs to a filtered collection."""
        for collection in obj.users_collection:
            name = collection.name or ""
            if name == "ref" or name.startswith("."):
                return True
        return False

    # Export all objects in the current scene to the staging directory
    staged_objects = [obj for obj in bpy.context.scene.objects if not should_ignore(obj)]
    for obj in staged_objects:
        obj_filename = f"{obj.name}.blend"
        bpy.data.libraries.write(
            filepath=str(staging_dir / obj_filename),
            datablocks={obj},
        )

    # Get list of current object filenames that were exported
    current_obj_files = {f"{obj.name}.blend" for obj in staged_objects}

    # Remove blend files in staging directory that no longer correspond to existing objects
    for blend_file in staging_dir.glob("*.blend"):
        if blend_file.name not in current_obj_files:
            blend_file.unlink()
            print(f"Removed orphaned file: {blend_file.name}")

    print("Save handler triggered - staging data...")
    # Only report if self is available (when called as operator)
    if self is not None:
        self.report({'INFO'}, "Staged current scene objects.")

#TODO: Handler for node_groups

#TODO: Handler for collections and scenes

#TODO: Handler for user settings

#TODO: Handler for dependencies