import bpy
from pathlib import Path

class GITBLEND_OT_Purge(bpy.types.Operator):
    bl_idname = "gitblend.purge"
    bl_label = "Purge Commits"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene.gitblend_props
        
        # Get the .gitblend directory
        if not bpy.data.filepath:
            self.report({'ERROR'}, "No file is currently open")
            return {'CANCELLED'}
            
        gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
        
        if not gitblend_dir.exists():
            self.report({'WARNING'}, "No .gitblend directory found")
            return {'CANCELLED'}
        
        # Delete all .blend files in .gitblend directory
        deleted_count = 0
        for file_path in gitblend_dir.glob("*.blend"):
            try:
                file_path.unlink()
                deleted_count += 1
            except OSError as e:
                self.report({'ERROR'}, f"Failed to delete {file_path.name}: {e}")
                return {'CANCELLED'}
        
        # Clear the commit history UI
        scene.commit_history.clear()
        scene.i = 0
        
        self.report({'INFO'}, f"Purged {deleted_count} commit(s)")
        return {'FINISHED'}