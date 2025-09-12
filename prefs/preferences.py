import bpy
import subprocess
import sys
import os
from pathlib import Path

class GITBLEND_OT_InstallJsondiff(bpy.types.Operator):
    """Install jsondiff module to Blender's modules directory"""
    bl_idname = "gitblend.install_jsondiff"
    bl_label = "Install jsondiff"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        try:
            # Blender's modules directory
            modules_dir = Path(bpy.utils.user_resource('SCRIPTS')) / "modules"
            modules_dir.mkdir(parents=True, exist_ok=True)
            
            # Install jsondiff using pip with target directory
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", 
                "jsondiff", "--target", str(modules_dir)
            ], capture_output=True, text=True, check=True)
            
            self.report({'INFO'}, f"jsondiff installed successfully to {modules_dir}")
            return {'FINISHED'}
            
        except subprocess.CalledProcessError as e:
            self.report({'ERROR'}, f"Failed to install jsondiff: {e.stderr}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error installing jsondiff: {str(e)}")
            return {'CANCELLED'}

class GITBLEND_OT_UninstallJsondiff(bpy.types.Operator):
    """Uninstall jsondiff module from Blender's modules directory"""
    bl_idname = "gitblend.uninstall_jsondiff"
    bl_label = "Uninstall jsondiff"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        try:
            # Blender's modules directory
            modules_dir = Path(bpy.utils.user_resource('SCRIPTS')) / "modules"
            
            # Find and remove jsondiff related files/directories
            removed_items = []
            
            # Remove jsondiff directory if it exists
            jsondiff_dir = modules_dir / "jsondiff"
            if jsondiff_dir.exists():
                import shutil
                shutil.rmtree(jsondiff_dir)
                removed_items.append("jsondiff/")
            
            # Remove jsondiff-*.dist-info directories
            for item in modules_dir.glob("jsondiff-*.dist-info"):
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item)
                    removed_items.append(item.name)
            
            # Remove any jsondiff*.py files
            for item in modules_dir.glob("jsondiff*.py"):
                if item.is_file():
                    item.unlink()
                    removed_items.append(item.name)
            
            if removed_items:
                self.report({'INFO'}, f"Removed: {', '.join(removed_items)}")
            else:
                self.report({'INFO'}, "jsondiff not found or already removed")
                
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error uninstalling jsondiff: {str(e)}")
            return {'CANCELLED'}

class GITBLEND_OT_CheckJsondiff(bpy.types.Operator):
    """Check if jsondiff module is available"""
    bl_idname = "gitblend.check_jsondiff"
    bl_label = "Check jsondiff"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        try:
            import jsondiff
            self.report({'INFO'}, f"jsondiff is available (version: {jsondiff.__version__})")
            return {'FINISHED'}
        except ImportError:
            self.report({'WARNING'}, "jsondiff is not installed or not accessible")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error checking jsondiff: {str(e)}")
            return {'CANCELLED'}

