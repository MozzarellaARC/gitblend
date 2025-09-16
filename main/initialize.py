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
	return {
		"version": METADATA_VERSION, 
		"commits": [],
		"branches": {
			"main": {
				"head_commit": None,
				"created_from": None,
				"created_at": None
			}
		},
		"current_branch": "main",
		"head_commit": None  # Points to the latest commit hash on current branch
	}


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
			
			# Ensure branch-related fields exist (for backwards compatibility)
			if 'branches' not in data:
				data['branches'] = {
					"main": {
						"head_commit": None,
						"created_from": None,
						"created_at": None
					}
				}
			if 'current_branch' not in data:
				data['current_branch'] = "main"
			if 'head_commit' not in data:
				# Set head_commit to the latest commit if any exist
				if data['commits']:
					data['head_commit'] = data['commits'][-1].get('hash')
					# Also update main branch head
					if 'main' in data['branches']:
						data['branches']['main']['head_commit'] = data['head_commit']
				else:
					data['head_commit'] = None
			
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


def save_metadata(project_dir: Path, metadata: Dict[str, Any]) -> None:
	"""Save metadata to .gitblend/metadata.json. Alias for write_metadata_atomic."""
	write_metadata_atomic(project_dir, metadata)


def append_commit(project_dir: Path, commit: Dict[str, Any]) -> None:
	data = load_metadata(project_dir)
	
	# Add branch information to commit
	current_branch = data.get('current_branch', 'main')
	commit['branch'] = current_branch
	
	data['commits'].append(commit)
	# Update head_commit to point to the latest commit
	commit_hash = commit.get('hash')
	if commit_hash:
		data['head_commit'] = commit_hash
		# Update current branch's head commit
		current_branch = data.get('current_branch', 'main')
		if current_branch in data.get('branches', {}):
			data['branches'][current_branch]['head_commit'] = commit_hash
	write_metadata_atomic(project_dir, data)


def get_branch_commits(project_dir: Path, branch_name: str) -> list:
	"""Get all commits that belong to a specific branch."""
	metadata = load_metadata(project_dir)
	commits = metadata.get('commits', [])
	
	# Get the branch info
	branch_info = metadata.get('branches', {}).get(branch_name)
	if not branch_info:
		# If branch doesn't exist, return empty list
		return []
	
	head_commit = branch_info.get('head_commit')
	created_from = branch_info.get('created_from')
	
	if not head_commit:
		return []
	
	# For proper branch filtering, we need to:
	# 1. Include all commits that have this branch as their 'branch' field
	# 2. Include common history up to the branch creation point
	
	branch_commits = []
	
	# First pass: collect commits that explicitly belong to this branch
	for commit in commits:
		commit_branch = commit.get('branch', 'main')  # Default to main if no branch info
		if commit_branch == branch_name:
			branch_commits.append(commit)
	
	# Second pass: if this branch was created from another commit,
	# include the history up to that point
	if created_from and branch_name != 'main':
		for commit in commits:
			# Include commits that come before the branch creation point
			if commit.get('hash') == created_from:
				branch_commits.append(commit)
				break
			# Include commits that are part of the main line up to creation point
			commit_branch = commit.get('branch', 'main')
			if commit_branch == 'main':
				branch_commits.append(commit)
	elif branch_name == 'main':
		# For main branch, show all commits that belong to main
		for commit in commits:
			commit_branch = commit.get('branch', 'main')
			if commit_branch == 'main':
				branch_commits.append(commit)
	
	# Remove duplicates while preserving order
	seen_hashes = set()
	filtered_commits = []
	for commit in branch_commits:
		commit_hash = commit.get('hash')
		if commit_hash not in seen_hashes:
			seen_hashes.add(commit_hash)
			filtered_commits.append(commit)
	
	return filtered_commits


def get_current_branch_commits(project_dir: Path) -> list:
	"""Get commits for the currently selected branch."""
	current_branch = get_current_branch(project_dir)
	return get_branch_commits(project_dir, current_branch)


def get_current_commit_hash(context) -> str:
	"""Get the hash of the currently checked out commit."""
	props = getattr(context.scene, "gitblend_props", None)
	if not props:
		return ""
	
	# Always use commits_index as the source of truth for the current commit
	# branch_commits is just a filtered view for display purposes
	if props.commits_index >= 0 and props.commits_index < len(props.commits):
		return props.commits[props.commits_index].hash
	
	return ""


def is_on_head_commit(context) -> bool:
	"""Check if the user is currently on the HEAD commit (latest commit on current branch)."""
	blend_path = bpy.data.filepath
	if not blend_path:
		return True  # Default to HEAD if no file
	
	project_dir = Path(blend_path).resolve().parent
	if not is_gitblend_initialized(project_dir):
		return True  # Default to HEAD if not initialized
	
	metadata = load_metadata(project_dir)
	head_commit = metadata.get('head_commit')
	current_commit = get_current_commit_hash(context)
	
	# If no commits exist yet, we're on HEAD
	if not head_commit:
		return True
	
	# If no current commit (empty commits list), we're on HEAD 
	if not current_commit:
		return True
	
	return head_commit == current_commit


def get_branch_names(project_dir: Path) -> list:
	"""Get list of all branch names."""
	metadata = load_metadata(project_dir)
	return list(metadata.get('branches', {}).keys())


def get_current_branch(project_dir: Path) -> str:
	"""Get the name of the current branch."""
	metadata = load_metadata(project_dir)
	return metadata.get('current_branch', 'main')


def create_branch(project_dir: Path, branch_name: str, from_commit_hash: str) -> None:
	"""Create a new branch from a specific commit."""
	import time
	data = load_metadata(project_dir)
	
	if 'branches' not in data:
		data['branches'] = {}
	
	# Create new branch entry
	data['branches'][branch_name] = {
		'head_commit': from_commit_hash,
		'created_from': from_commit_hash,
		'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
	}
	
	# Switch to the new branch
	data['current_branch'] = branch_name
	
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


def is_ui_synced_with_metadata(context) -> bool:
	"""Check if the UI commit list is synchronized with the metadata file."""
	blend_path = bpy.data.filepath
	if not blend_path:
		return False
	
	project_dir = Path(blend_path).resolve().parent
	if not is_gitblend_initialized(project_dir):
		return False
	
	props = getattr(context.scene, "gitblend_props", None)
	if not props:
		return False
	
	# Load metadata
	metadata = load_metadata(project_dir)
	metadata_commits = metadata.get('commits', [])
	
	# Compare counts first
	if len(props.commits) != len(metadata_commits):
		return False
	
	# Compare each commit
	for i, ui_commit in enumerate(props.commits):
		if i >= len(metadata_commits):
			return False
		metadata_commit = metadata_commits[i]
		if (ui_commit.hash != metadata_commit.get('hash', '') or
		    ui_commit.message != metadata_commit.get('message', '') or
		    ui_commit.timestamp != metadata_commit.get('timestamp', '')):
			return False
	
	return True


def update_branch_status(context) -> None:
	"""Update the branch status properties in the UI."""
	props = getattr(context.scene, "gitblend_props", None)
	if not props:
		return
	
	blend_path = bpy.data.filepath
	if not blend_path:
		props.current_branch_display = "main"
		props.is_on_head = True
		props.branch_enum = "main"
		return
	
	try:
		project_dir = Path(blend_path).resolve().parent
		if not is_gitblend_initialized(project_dir):
			props.current_branch_display = "main"
			props.is_on_head = True
			props.branch_enum = "main"
			return
		
		# Update current branch display
		current_branch = get_current_branch(project_dir)
		props.current_branch_display = current_branch
		
		# Update branch enum to current branch (without triggering callback)
		# We need to temporarily disable the update callback
		wm = context.window_manager if hasattr(context, 'window_manager') else None
		if wm:
			wm['gitblend_loading_history'] = True
		try:
			props.branch_enum = current_branch
		finally:
			if wm and 'gitblend_loading_history' in wm:
				del wm['gitblend_loading_history']
		
		# Update HEAD status
		was_on_head = props.is_on_head
		props.is_on_head = is_on_head_commit(context)
		
		# Auto-populate branch name when switching from HEAD to DETACHED
		if was_on_head and not props.is_on_head:
			# User just switched to detached state, suggest branch name from commit message
			current_commit_hash = get_current_commit_hash(context)
			if current_commit_hash and props.commits:
				for commit in props.commits:
					if commit.hash == current_commit_hash:
						# Use commit message as suggested branch name
						suggested_name = commit.message.strip()
						if suggested_name:
							# Sanitize the name
							import re
							suggested_name = re.sub(r'[^\w\s-]', '', suggested_name)[:50]
							suggested_name = re.sub(r'\s+', '_', suggested_name)
							if suggested_name:
								props.branch_name = suggested_name
						break
		
		# Refresh branch commits when branch status changes
		try:
			populate_branch_commits(context)
			sync_commit_indices(context)
		except Exception:
			pass
		
	except Exception:
		props.current_branch_display = "main"
		props.is_on_head = True
		props.branch_enum = "main"


def get_commit_branches(project_dir: Path, commit_hash: str) -> list:
	"""Get all branches that were created from a specific commit."""
	metadata = load_metadata(project_dir)
	branches = metadata.get('branches', {})
	
	commit_branches = []
	for branch_name, branch_info in branches.items():
		if branch_info.get('created_from') == commit_hash:
			commit_branches.append(branch_name)
	
	return commit_branches


def has_branches_from_commit(project_dir: Path, commit_hash: str) -> bool:
	"""Check if any branches were created from this commit."""
	return len(get_commit_branches(project_dir, commit_hash)) > 0


def is_branch_empty(project_dir: Path, branch_name: str) -> bool:
	"""Check if a branch has no commits (was created but never committed to)."""
	metadata = load_metadata(project_dir)
	branch_info = metadata.get('branches', {}).get(branch_name)
	if not branch_info:
		return True
	
	created_from = branch_info.get('created_from')
	head_commit = branch_info.get('head_commit')
	
	# If head_commit is the same as created_from, the branch has no new commits
	return created_from == head_commit


def should_show_commit_button_on_detached(context) -> bool:
	"""Determine if commit button should be shown when detached (vs create branch button)."""
	blend_path = bpy.data.filepath
	if not blend_path:
		return False
	
	project_dir = Path(blend_path).resolve().parent
	if not is_gitblend_initialized(project_dir):
		return False
	
	props = getattr(context.scene, "gitblend_props", None)
	if not props:
		return False
	
	# Get current commit and selected branch
	current_commit_hash = get_current_commit_hash(context)
	selected_branch = props.branch_enum
	
	if not current_commit_hash or not selected_branch:
		return False
	
	# Check if this commit has branches created from it
	if not has_branches_from_commit(project_dir, current_commit_hash):
		return False
	
	# Check if the selected branch is empty (no commits yet)
	if not is_branch_empty(project_dir, selected_branch):
		return False
	
	# Check if the selected branch was created from this commit
	commit_branches = get_commit_branches(project_dir, current_commit_hash)
	return selected_branch in commit_branches


def sync_commit_indices(context) -> None:
	"""Ensure both commits_index and branch_commits_index point to the same commit."""
	props = getattr(context.scene, "gitblend_props", None)
	if not props:
		return
	
	# Get the current commit hash from the main index
	current_hash = ""
	if props.commits_index >= 0 and props.commits_index < len(props.commits):
		current_hash = props.commits[props.commits_index].hash
	
	if not current_hash:
		return
	
	# Find this commit in branch_commits and update the index
	for i, branch_commit in enumerate(props.branch_commits):
		if branch_commit.hash == current_hash:
			props.branch_commits_index = i
			break


def populate_branch_commits(context, branch_name: str = None) -> None:
	"""Populate the branch-filtered commits collection."""
	blend_path = bpy.data.filepath
	if not blend_path:
		return
	
	project_dir = Path(blend_path).resolve().parent
	if not is_gitblend_initialized(project_dir):
		return
	
	props = getattr(context.scene, "gitblend_props", None)
	if not props:
		return
	
	# Use current branch if not specified
	if branch_name is None:
		branch_name = get_current_branch(project_dir)
	
	# Get commits for the specified branch
	branch_commits = get_branch_commits(project_dir, branch_name)
	
	# Clear and populate branch_commits collection
	props.branch_commits.clear()
	current_commit_hash = get_current_commit_hash(context)
	selected_index = -1
	
	for i, commit_data in enumerate(branch_commits):
		entry = props.branch_commits.add()
		entry.hash = commit_data.get('hash', '')
		entry.message = commit_data.get('message', '')
		entry.timestamp = commit_data.get('timestamp', '')
		
		# Track the currently selected commit index
		if entry.hash == current_commit_hash:
			selected_index = i
	
	# Set the active index
	if selected_index >= 0:
		props.branch_commits_index = selected_index
	elif props.branch_commits:
		props.branch_commits_index = len(props.branch_commits) - 1
	else:
		props.branch_commits_index = -1


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

	wm = context.window_manager if hasattr(context, 'window_manager') else None
	if wm:
		wm['gitblend_loading_history'] = True  # Suppress auto-checkout during population
	try:
		# Clear existing entries
		props.commits.clear()

		# Load metadata and populate UI
		metadata = load_metadata(project_dir)
		
		# Check if metadata was migrated and save it
		original_metadata = {}
		try:
			path = get_metadata_path(project_dir)
			if path.exists():
				with path.open('r', encoding='utf-8') as f:
					original_metadata = json.load(f)
		except Exception:
			pass
		
		# If metadata structure was updated, save the migrated version
		if ('branches' not in original_metadata or 
		    'current_branch' not in original_metadata or 
		    'head_commit' not in original_metadata):
			try:
				write_metadata_atomic(project_dir, metadata)
			except Exception:
				pass
		
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
		
		# Update branch status
		update_branch_status(context)
		
		# Populate branch-specific commits
		populate_branch_commits(context)
	finally:
		if wm and 'gitblend_loading_history' in wm:
			del wm['gitblend_loading_history']


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
	'is_gitblend_initialized', 'populate_ui_from_metadata', 'is_ui_synced_with_metadata',
	'is_on_head_commit', 'get_current_commit_hash', 'get_branch_names', 'get_current_branch',
	'create_branch', 'update_branch_status', 'populate_branch_commits', 'get_branch_commits',
	'get_current_branch_commits', 'sync_commit_indices'
]