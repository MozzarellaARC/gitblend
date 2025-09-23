import bpy
from pathlib import Path

def stage_handler(self, context):

    # Ensure .gitblend directory exists
    gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
    if not bpy.data.filepath:
        self.report({'ERROR'}, ".gitblend not initialized")
        return {'CANCELLED'}

    staging_dir = gitblend_dir / "staging"
    staging_dir.mkdir(exist_ok=True)
    
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