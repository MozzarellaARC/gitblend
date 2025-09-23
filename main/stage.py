import bpy
from pathlib import Path

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
    
    # Export all objects in the current scene to the staging directory
    for obj in bpy.context.scene.objects:
        obj_filename = f"{obj.name}.blend"
        bpy.data.libraries.write(
            filepath=str(staging_dir / obj_filename),
            datablocks={obj},
        )

    # Get list of current object filenames that were exported
    current_obj_files = {f"{obj.name}.blend" for obj in bpy.context.scene.objects}

    # Remove blend files in staging directory that no longer correspond to existing objects
    for blend_file in staging_dir.glob("*.blend"):
        if blend_file.name not in current_obj_files:
            blend_file.unlink()
            print(f"Removed orphaned file: {blend_file.name}")

    print("Save handler triggered - staging data...")

#TODO: Handler for node_groups

#TODO: Handler for collections and scenes

#TODO: Handler for user settings

#TODO: Handler for dependencies