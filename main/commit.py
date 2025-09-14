import bpy
import hashlib
import os
import time
from pathlib import Path

# Metadata dependency
import json
from typing import Dict, Any
from ..prefs.constants import METADATA_FILENAME, METADATA_VERSION


def get_metadata_path(project_dir: Path) -> Path:
    return project_dir / '.gitblend' / METADATA_FILENAME


def _default_structure() -> Dict[str, Any]:
    return {"version": METADATA_VERSION, "commits": []}


def load_metadata(project_dir: Path) -> Dict[str, Any]:
    path = get_metadata_path(project_dir)
    if not path.exists():
        return _default_structure()
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            # Basic sanity checks
            if not isinstance(data, dict):
                return _default_structure()
            if 'commits' not in data or not isinstance(data['commits'], list):
                data['commits'] = []
            data.setdefault('version', METADATA_VERSION)
            return data
    except Exception:
        return _default_structure()


def append_commit(project_dir: Path, commit: Dict[str, Any]) -> None:
    """Append a commit entry and write atomically."""
    data = load_metadata(project_dir)
    data['commits'].append(commit)
    metadata_path = get_metadata_path(project_dir)
    metadata_path.parent.mkdir(exist_ok=True)
    tmp_path = metadata_path.with_suffix('.tmp')
    with tmp_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, metadata_path)


def _compute_scene_hash(scene: bpy.types.Scene) -> str:
    """Compute a sha-256 hash representing the current scene state.
    For now we use a combination of object names, modification times and a timestamp
    to ensure uniqueness. This can evolve into a deterministic content hash later.
    """
    h = hashlib.sha256()
    # Basic entropy: object names and counts
    try:
        for obj in scene.objects:
            h.update(obj.name.encode('utf-8', 'ignore'))
            h.update(str(obj.type).encode())
    except Exception:
        pass
    # Add current time to guarantee uniqueness even if scene unchanged
    h.update(str(time.time_ns()).encode())
    return h.hexdigest()


class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit changes to the Git repository"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = getattr(context.scene, "gitblend_props", None)
        commit_message = (props.commit_message if props else "").strip()

        if not commit_message:
            self.report({'ERROR'}, "Commit message cannot be empty.")
            return {'CANCELLED'}
        # Determine current working .blend file path
        current_filepath = bpy.data.filepath
        if not current_filepath:
            self.report({'ERROR'}, "Please save the .blend file before committing.")
            return {'CANCELLED'}

        current_dir = Path(current_filepath).resolve().parent
        gitblend_dir = current_dir / '.gitblend'
        try:
            gitblend_dir.mkdir(exist_ok=True)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create .gitblend directory: {e}")
            return {'CANCELLED'}

        # Compute a unique sha-256 filename
        scene_hash = _compute_scene_hash(context.scene)
        snapshot_path = gitblend_dir / f"{scene_hash}.blend"

        # Save snapshot without altering the currently open file (copy=True)
        try:
            bpy.ops.wm.save_as_mainfile(filepath=str(snapshot_path), copy=True)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save snapshot: {e}")
            return {'CANCELLED'}

        # Record commit in in-memory history (UI list)
        timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S')
        if props:
            entry = props.commits.add()
            entry.hash = scene_hash
            entry.message = commit_message
            entry.timestamp = timestamp_str
            props.commits_index = len(props.commits) - 1
            # Clear message after commit
            props.commit_message = ""
        # Persist commit metadata
        try:
            append_commit(current_dir, {
                "hash": scene_hash,
                "message": commit_message,
                "timestamp": timestamp_str,
                "snapshot": snapshot_path.name,
            })
        except Exception as e:
            self.report({'WARNING'}, f"Metadata write failed: {e}")
        # Force UI redraw
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        self.report({'INFO'}, f"Committed snapshot {snapshot_path.name} : {commit_message}")
        return {'FINISHED'}
    
