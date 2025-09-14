import bpy
from pathlib import Path
from typing import Dict, Any
import json
import os

from ..prefs.constants import METADATA_FILENAME, METADATA_VERSION

# -------- .gitblend metadata helpers (moved from commit.py) -------- #

def get_gitblend_dir(project_dir: Path) -> Path:
	"""Return the path to the .gitblend directory within a project directory."""
	return project_dir / '.gitblend'


def get_metadata_path(project_dir: Path) -> Path:
	return get_gitblend_dir(project_dir) / METADATA_FILENAME


def _default_structure() -> Dict[str, Any]:
	return {"version": METADATA_VERSION, "commits": []}


def ensure_gitblend_dir(project_dir: Path) -> Path:
	"""Ensure the .gitblend directory exists. Return its path.

	Raises OSError on failure so callers (operators) can report errors.
	"""
	gb_dir = get_gitblend_dir(project_dir)
	gb_dir.mkdir(exist_ok=True)
	return gb_dir


def load_metadata(project_dir: Path) -> Dict[str, Any]:
	path = get_metadata_path(project_dir)
	if not path.exists():
		return _default_structure()
	try:
		with path.open('r', encoding='utf-8') as f:
			data = json.load(f)
			if not isinstance(data, dict):
				return _default_structure()
			if 'commits' not in data or not isinstance(data['commits'], list):
				data['commits'] = []
			data.setdefault('version', METADATA_VERSION)
			return data
	except Exception:
		return _default_structure()


def write_metadata_atomic(project_dir: Path, data: Dict[str, Any]) -> None:
	metadata_path = get_metadata_path(project_dir)
	metadata_path.parent.mkdir(exist_ok=True)
	tmp_path = metadata_path.with_suffix('.tmp')
	with tmp_path.open('w', encoding='utf-8') as f:
		json.dump(data, f, indent=2)
	os.replace(tmp_path, metadata_path)


def append_commit(project_dir: Path, commit: Dict[str, Any]) -> None:
	data = load_metadata(project_dir)
	data['commits'].append(commit)
	write_metadata_atomic(project_dir, data)


def initialize_gitblend(project_dir: Path) -> None:
	"""High level initialization: ensure directory and base metadata file exists."""
	ensure_gitblend_dir(project_dir)
	metadata_path = get_metadata_path(project_dir)
	if not metadata_path.exists():
		write_metadata_atomic(project_dir, _default_structure())

def is_gitblend_initialized(project_dir: Path) -> bool:
	"""Return True if .gitblend directory and metadata file exist."""
	metadata_path = get_metadata_path(project_dir)
	return metadata_path.exists()


def populate_ui_from_metadata(context) -> None:
	"""Populate the UI list with commits from metadata file."""
	blend_path = bpy.data.filepath
	if not blend_path:
		return
	
	project_dir = Path(blend_path).resolve().parent
	if not is_gitblend_initialized(project_dir):
		return
	
	props = getattr(context.scene, "gitblend_props", None)
	if not props:
		return
	
	# Clear existing entries
	props.commits.clear()
	
	# Load metadata and populate UI
	metadata = load_metadata(project_dir)
	for commit_data in metadata.get('commits', []):
		entry = props.commits.add()
		entry.hash = commit_data.get('hash', '')
		entry.message = commit_data.get('message', '')
		entry.timestamp = commit_data.get('timestamp', '')
	
	# Set active index to the last commit
	if props.commits:
		props.commits_index = len(props.commits) - 1
	else:
		props.commits_index = -1


class GITBLEND_OT_sync(bpy.types.Operator):
	"""Sync operator to populate the UI with existing commit history."""
	bl_idname = "gitblend.sync"
	bl_label = "Sync History"
	bl_description = "Load existing commit history from .gitblend directory"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		# Only enabled if file is saved and .gitblend exists
		blend_path = bpy.data.filepath
		if not blend_path:
			return False
		try:
			project_dir = Path(blend_path).resolve().parent
			return is_gitblend_initialized(project_dir)
		except Exception:
			return False

	def execute(self, context):
		try:
			populate_ui_from_metadata(context)
			self.report({'INFO'}, "Commit history synchronized")
			return {'FINISHED'}
		except Exception as e:
			self.report({'ERROR'}, f"Failed to sync history: {e}")
			return {'CANCELLED'}


class GITBLEND_OT_initialize(bpy.types.Operator):
	bl_idname = "gitblend.initialize"
	bl_label = "Initialize .gitblend"
	bl_description = "Create the .gitblend folder and metadata file next to the current .blend"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):  # type: ignore
		# Only enabled if file saved
		return bool(bpy.data.filepath)

	def execute(self, context):  # type: ignore
		blend_path = bpy.data.filepath
		if not blend_path:
			self.report({'ERROR'}, "Please save the .blend file first.")
			return {'CANCELLED'}
		
		project_dir = Path(blend_path).resolve().parent
		
		try:
			# Check if .gitblend already exists
			if is_gitblend_initialized(project_dir):
				# .gitblend exists, sync the commit history
				populate_ui_from_metadata(context)
				self.report({'INFO'}, "Synchronized with existing .gitblend repository")
			else:
				# Initialize new .gitblend
				initialize_gitblend(project_dir)
				self.report({'INFO'}, ".gitblend initialized")
		except Exception as e:  # pragma: no cover - Blender runtime context
			self.report({'ERROR'}, f"Operation failed: {e}")
			return {'CANCELLED'}
		
		return {'FINISHED'}


__all__ = [
	'get_gitblend_dir', 'get_metadata_path', 'initialize_gitblend', 'append_commit',
	'ensure_gitblend_dir', 'load_metadata', 'GITBLEND_OT_initialize', 'GITBLEND_OT_sync', 
	'is_gitblend_initialized', 'populate_ui_from_metadata'
]