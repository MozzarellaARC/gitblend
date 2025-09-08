import bpy  # type: ignore
import os
from typing import Iterable, List, Optional, Tuple
import hashlib


def _ensure_collection(name: Optional[str]) -> bpy.types.Collection:
	"""Return a destination collection; create it under the Scene collection if needed.

	If name is falsy, return the active scene root collection.
	"""
	scene = bpy.context.scene
	if not name:
		return scene.collection
	col = bpy.data.collections.get(name)
	if col is None:
		col = bpy.data.collections.new(name)
		# Link under the Scene's master collection
		try:
			scene.collection.children.link(col)
		except Exception:
			# If already linked or linking fails, ignore; collection still exists in data
			pass
	return col


def _resolve_blender_path(path_str: str) -> str:
	"""Resolve Blender-style paths (supports // relative) to absolute filesystem paths.

	- Uses bpy.path.abspath; when the current .blend is unsaved, fall back to CWD for //.
	- If a Blender library subpath is provided (e.g., my.blend\Object\), strip after .blend.
	"""
	if not path_str:
		return ""
	try:
		start = None if getattr(bpy.data, "is_saved", False) else os.getcwd()
		resolved = bpy.path.abspath(path_str, start=start)
	except Exception:
		resolved = os.path.expandvars(os.path.expanduser(path_str))

	# Normalize and strip any trailing library subpath after .blend
	p = os.path.normpath(resolved)
	low = p.lower()
	if ".blend" in low:
		idx = low.rfind(".blend")
		candidate = p[: idx + len(".blend")]
		if os.path.exists(candidate):
			p = candidate
	return p
def open_base_blend(path_str: str) -> str:
	"""Open a .blend file as the current mainfile. Returns the resolved path.

	Intended for headless/CLI use. In a UI session it will replace the current file.
	"""
	p = _resolve_blender_path(path_str)
	if not p or not os.path.exists(p):
		raise FileNotFoundError(f"Base .blend not found: {path_str} -> {p}")
	bpy.ops.wm.open_mainfile(filepath=p)
	return p



def append_objects_from_blend(
	source_blend_path: str,
	object_names: Iterable[str],
	dest_collection_name: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
	"""Append objects by name from another .blend file.

	Returns (appended_names, missing_names).
	"""
	src = _resolve_blender_path(source_blend_path or "")
	if not src or not os.path.exists(src):
		raise FileNotFoundError(f"Source .blend not found: {source_blend_path} -> {src}")

	names = [n for n in (object_names or []) if (n or "").strip()]
	if not names:
		raise ValueError("No object names provided to append.")

	dest_coll = _ensure_collection(dest_collection_name)

	available: List[str] = []
	loaded_objs: List[Optional[bpy.types.Object]] = []  # type: ignore
	missing: List[str] = []
	appended: List[str] = []

	# Load datablocks using library API (append = link False)
	with bpy.data.libraries.load(src, link=False) as (data_from, data_to):
		available = list(data_from.objects or [])
		to_load = [n for n in names if n in available]
		missing = [n for n in names if n not in available]
		data_to.objects = to_load

	# After leaving the context, data_to.objects contains actual datablocks
	try:
		loaded_objs = [ob for ob in (data_to.objects or [])]  # type: ignore
	except Exception:
		loaded_objs = []

	# Link objects to destination collection if not already linked
	for ob in loaded_objs:
		if ob is None:
			continue
		try:
			# If it's not in any collection, link it to destination
			if not ob.users_collection:
				dest_coll.objects.link(ob)
		except Exception:
			# If linking fails (e.g. already linked), best-effort continue
			pass
		appended.append(ob.name)

	return appended, missing


def save_blend(save_as: Optional[str] = None) -> str:
	"""Save the current .blend. If save_as is provided, save to that path.

	Returns the absolute path written.
	"""
	if save_as:
		target = os.path.abspath(save_as)
		# Ensure parent directory exists
		parent = os.path.dirname(target)
		if parent and not os.path.exists(parent):
			os.makedirs(parent, exist_ok=True)
		bpy.ops.wm.save_as_mainfile(filepath=target, copy=False)
		return target
	else:
		# Save in place
		bpy.ops.wm.save_mainfile()
		return bpy.data.filepath


def export_snapshot_blend(project_dir: str, branch: str, uid: str) -> Tuple[str, str]:
	"""Save a copy of the current .blend into the gitblend snapshot store and return (path, sha256).

	The file is written to: <project_dir>/.gitblend/snapshots/<branch>/<uid>.blend
	"""
	branch = (branch or "main").strip() or "main"
	uid = (uid or "").strip() or "snapshot"

	out_dir = os.path.join(project_dir, ".gitblend", "snapshots", branch)
	os.makedirs(out_dir, exist_ok=True)
	out_path = os.path.abspath(os.path.join(out_dir, f"{uid}.blend"))

	# Write a copy without changing current file path
	bpy.ops.wm.save_as_mainfile(filepath=out_path, copy=True)

	# Compute sha256
	h = hashlib.sha256()
	with open(out_path, "rb") as f:
		for chunk in iter(lambda: f.read(1024 * 1024), b""):
			h.update(chunk)
	return out_path, h.hexdigest()
