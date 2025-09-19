import bpy
import os
import json
import hashlib
import time
from datetime import datetime
from pathlib import Path


class GITBLEND_OT_RefreshStatus(bpy.types.Operator):
    bl_idname = "gitblend.refresh_status"
    bl_label = "Refresh Status"
    bl_description = "Refresh the initialization status"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        check_and_update_initialized_property(context)
        return {'FINISHED'}


class GITBLEND_OT_Initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Initialize git blend repository for this .blend file"
    bl_options = {'REGISTER', 'UNDO'}
    
    commit_message: bpy.props.StringProperty(
        name="Initial Commit Message",
        description="Message for the initial commit",
        default="Initial commit"
    )
    
    @classmethod
    def poll(cls, context):
        # Can only initialize if blend file is saved
        return bpy.data.filepath != ""
    
    def execute(self, context):
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        
        # Check if .gitblend already exists
        if gitblend_dir.exists():
            self.report({'INFO'}, "Git Blend already initialized")
            return {'CANCELLED'}
        
        try:
            # Create .gitblend directory
            gitblend_dir.mkdir()
            
            # Generate commit hash using current timestamp and content
            timestamp = datetime.now().isoformat()
            current_time = int(time.time())
            
            # Create initial commit metadata
            commit_data = {
                "hash": self._generate_commit_hash(current_time, self.commit_message),
                "timestamp": timestamp,
                "message": self.commit_message,
                "parent": None  # Initial commit has no parent
            }
            
            # Save initial metadata
            metadata_file = gitblend_dir / "commits.json"
            metadata = {
                "version": 1,
                "commits": [commit_data]
            }
            
            with metadata_file.open('w') as f:
                json.dump(metadata, f, indent=2)
            
            # Export data blocks to .blend file
            blend_filename = f"{commit_data['hash']}.blend"
            blend_export_path = gitblend_dir / blend_filename
            
            self._export_data_blocks(str(blend_export_path))
            
            # Create initial signature file for change detection
            signature_file = gitblend_dir / f"{commit_data['hash']}_signature.json"
            initial_signature = self._generate_initial_signature()
            with signature_file.open('w') as f:
                json.dump(initial_signature, f, indent=2)
            
            # Update initialized property
            context.scene.gitblend_props.initialized = True
            
            self.report({'INFO'}, f"Git Blend initialized with commit: {commit_data['hash'][:8]}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to initialize: {str(e)}")
            return {'CANCELLED'}
    
    def _generate_commit_hash(self, timestamp, message):
        """Generate SHA-256 hash for commit"""
        content = f"{timestamp}_{message}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _export_data_blocks(self, export_path):
        """Export specified data blocks using bpy.data.libraries.write"""
        # Data blocks to export as specified in data.instructions.md
        data_blocks = {
            'objects': bpy.data.objects,
            'meshes': bpy.data.meshes,
            'materials': bpy.data.materials,
            'images': bpy.data.images,
            'texts': bpy.data.texts,
            'actions': bpy.data.actions
        }
        
        # Collect all data blocks to write
        data_blocks_to_write = set()
        
        for block_type, collection in data_blocks.items():
            for item in collection:
                data_blocks_to_write.add(item)
        
        # Write to .blend file
        bpy.data.libraries.write(export_path, data_blocks_to_write, fake_user=True)
    
    def _generate_initial_signature(self):
        """Generate signature for initial commit (same as commit signature)"""
        signature = {
            "objects": {},
            "meshes": {},
            "materials": {},
            "images": {},
            "texts": {},
            "actions": {}
        }
        
        # Objects signature
        for obj in bpy.data.objects:
            obj_sig = {
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location) if hasattr(obj, 'location') else None,
                "rotation": list(obj.rotation_euler) if hasattr(obj, 'rotation_euler') else None,
                "scale": list(obj.scale) if hasattr(obj, 'scale') else None,
                "data_name": obj.data.name if obj.data else None
            }
            signature["objects"][obj.name] = obj_sig
        
        # Meshes signature
        for mesh in bpy.data.meshes:
            mesh_sig = {
                "name": mesh.name,
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "materials": [mat.name if mat else None for mat in mesh.materials]
            }
            signature["meshes"][mesh.name] = mesh_sig
        
        # Materials signature
        for mat in bpy.data.materials:
            mat_sig = {
                "name": mat.name,
                "use_nodes": mat.use_nodes,
                "diffuse_color": list(mat.diffuse_color) if hasattr(mat, 'diffuse_color') else None
            }
            signature["materials"][mat.name] = mat_sig
        
        # Images signature
        for img in bpy.data.images:
            img_sig = {
                "name": img.name,
                "size": list(img.size) if hasattr(img, 'size') else None,
                "filepath": img.filepath if hasattr(img, 'filepath') else None,
                "file_format": img.file_format if hasattr(img, 'file_format') else None
            }
            signature["images"][img.name] = img_sig
        
        # Texts signature
        for text in bpy.data.texts:
            text_sig = {
                "name": text.name,
                "lines_count": len(text.lines) if hasattr(text, 'lines') else 0,
                "content_hash": hashlib.md5(text.as_string().encode()).hexdigest() if hasattr(text, 'as_string') else None
            }
            signature["texts"][text.name] = text_sig
        
        # Actions signature
        for action in bpy.data.actions:
            action_sig = {
                "name": action.name,
                "frame_range": list(action.frame_range) if hasattr(action, 'frame_range') else None,
                "fcurves_count": len(action.fcurves) if hasattr(action, 'fcurves') else 0
            }
            signature["actions"][action.name] = action_sig
        
        return signature
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def register_initialize():
    bpy.utils.register_class(GITBLEND_OT_RefreshStatus)
    bpy.utils.register_class(GITBLEND_OT_Initialize)
    # Add handlers to check initialization status
    bpy.app.handlers.load_post.append(on_file_load_check_initialization)
    bpy.app.handlers.save_post.append(on_file_save_check_initialization)


def unregister_initialize():
    # Remove handlers
    if on_file_load_check_initialization in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load_check_initialization)
    if on_file_save_check_initialization in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_file_save_check_initialization)
    bpy.utils.unregister_class(GITBLEND_OT_Initialize)
    bpy.utils.unregister_class(GITBLEND_OT_RefreshStatus)


@bpy.app.handlers.persistent
def on_file_load_check_initialization(dummy):
    """Handler to check initialization status when a blend file is loaded"""
    try:
        context = bpy.context
        check_and_update_initialized_property(context)
    except Exception:
        pass  # Silently fail if context is not available


@bpy.app.handlers.persistent
def on_file_save_check_initialization(dummy):
    """Handler to check initialization status when a blend file is saved"""
    try:
        context = bpy.context
        check_and_update_initialized_property(context)
    except Exception:
        pass  # Silently fail if context is not available


# Utility functions for other modules
def is_gitblend_initialized(project_dir):
    """Check if .gitblend directory exists"""
    return (project_dir / ".gitblend").exists()


def check_and_update_initialized_property(context):
    """Check if gitblend is initialized and update the property accordingly"""
    if not bpy.data.filepath:
        context.scene.gitblend_props.initialized = False
        return False
    
    try:
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        is_initialized = is_gitblend_initialized(project_dir)
        context.scene.gitblend_props.initialized = is_initialized
        return is_initialized
    except Exception:
        context.scene.gitblend_props.initialized = False
        return False


def check_initialized_status(context):
    """Read-only check of initialization status - safe to call from panel draw"""
    if not bpy.data.filepath:
        return False
    
    try:
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        return is_gitblend_initialized(project_dir)
    except Exception:
        return False


def populate_ui_from_metadata(context):
    """Load commit history from metadata file into UI"""
    blend_path = Path(bpy.data.filepath).resolve()
    project_dir = blend_path.parent
    metadata_file = project_dir / ".gitblend" / "commits.json"
    
    if not metadata_file.exists():
        return
    
    try:
        with metadata_file.open('r') as f:
            metadata = json.load(f)
        
        props = context.scene.gitblend_props
        props.commits.clear()
        
        for commit in metadata.get('commits', []):
            commit_entry = props.commits.add()
            commit_entry.hash = commit.get('hash', '')
            commit_entry.message = commit.get('message', '')
            commit_entry.timestamp = commit.get('timestamp', '')
            
    except Exception as e:
        print(f"Failed to load metadata: {e}")


def has_branches_from_commit(project_dir, commit_hash):
    """Check if commit has branches (placeholder for future implementation)"""
    return False


def update_branch_status(context):
    """Update branch status in UI (placeholder for future implementation)"""
    props = context.scene.gitblend_props
    props.current_branch_display = "main"
    props.is_on_head = True


def get_branch_names(project_dir):
    """Get list of branch names (placeholder for future implementation)"""
    return ["main"]


def populate_branch_commits(context):
    """Populate branch-specific commits (placeholder for future implementation)"""
    props = context.scene.gitblend_props
    # For now, just copy all commits to branch_commits
    props.branch_commits.clear()
    for commit in props.commits:
        branch_commit = props.branch_commits.add()
        branch_commit.hash = commit.hash
        branch_commit.message = commit.message
        branch_commit.timestamp = commit.timestamp


def should_show_commit_button_on_detached(context):
    """Check if commit button should be shown when detached (placeholder)"""
    return False