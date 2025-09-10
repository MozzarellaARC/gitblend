import bpy
import re
from math import isclose
from typing import Dict, Iterable, List, Optional, Set, Tuple
from ..main.index import compute_collection_signature, derive_changed_set
from ..main.cas import get_latest_commit_objects
from .utils import (
    iter_objects_recursive,
    build_name_map,
    duplicate_object_with_data,
	remap_references_for_objects,
	get_object_dependencies,
)

from ..prefs.properties import SCENE_DIR, HIDDEN_SCENE_DIR


# Tolerances for float comparisons (relaxed slightly to avoid noise-based false positives)
EPS = 1e-5
EPS_POS = 5e-4  # looser for world positions

# Regex for extracting UIDs from snapshot names
_UID_RE = re.compile(r"_(\d{10,20})(?:-\d+)?$")

# =============================
# Collection/Object utilities
# (moved from manager_collection)
# =============================

def iter_objects_recursive(coll: bpy.types.Collection) -> Iterable[bpy.types.Object]:
	"""Iterate over all objects in a collection and its children recursively."""
	for obj in coll.objects:
		yield obj
	for child in coll.children:
		yield from iter_objects_recursive(child)


def extract_original_name(id_block) -> Optional[str]:
	"""Extract the original name from an object or collection, falling back to base name."""
	try:
		v = id_block.get("gitblend_orig_name", None)
		if isinstance(v, str) and v:
			return v
	except Exception:
		pass
	# Fallback: strip UID suffix
	name = getattr(id_block, "name", "") or ""
	m = _UID_RE.search(name)
	return name[:m.start()] if m else name


def build_name_map(coll: bpy.types.Collection, snapshot: bool = False) -> Dict[str, bpy.types.Object]:
	"""Build a mapping from object names to objects.

	Args:
		coll: Collection to map
		snapshot: If True, use stored original names; if False, use current names

	Returns:
		Dict mapping names to objects (first occurrence wins for duplicates)
	"""
	name_map: Dict[str, bpy.types.Object] = {}
	for obj in iter_objects_recursive(coll):
		name = extract_original_name(obj) if snapshot else (obj.name or "")
		if name and name not in name_map:
			name_map[name] = obj
	return name_map


def find_containing_collection(root_coll: bpy.types.Collection, target_obj: bpy.types.Object) -> Optional[bpy.types.Collection]:
	"""Find the collection that directly contains the target object."""
	# Check if target_obj is directly in this collection
	for obj in root_coll.objects:
		if obj == target_obj:
			return root_coll

	# Search in child collections
	for child in root_coll.children:
		found = find_containing_collection(child, target_obj)
		if found:
			return found
	return None


def path_to_collection(root_coll: bpy.types.Collection, target_coll: bpy.types.Collection) -> List[bpy.types.Collection]:
	"""Find the path from root collection to target collection."""
	path: List[bpy.types.Collection] = []
	found = False

	def dfs(c: bpy.types.Collection, acc: List[bpy.types.Collection]):
		nonlocal path, found
		if found:
			return
		acc.append(c)
		if c == target_coll:
			path = list(acc)
			found = True
		else:
			for ch in c.children:
				dfs(ch, acc)
				if found:
					break
		acc.pop()

	dfs(root_coll, [])
	return path if found else []


def list_branch_snapshots(scene: bpy.types.Scene, branch: str, max_uid: Optional[str] = None) -> List[bpy.types.Collection]:
	"""List all snapshot collections for a branch, optionally up to a maximum UID.

	Args:
		scene: Blender scene
		branch: Branch name to filter by
		max_uid: If provided, only include snapshots with UID <= max_uid

	Returns:
		List of snapshot collections, sorted by UID descending (newest first)
	"""
	# Find .gitblend collection
	dot_coll = None
	for c in scene.collection.children:
		if c.name == ".gitblend":
			dot_coll = c
			break

	if not dot_coll:
		return []

	# Build a set of snapshot names recorded in the index for this branch (for disambiguation)
	try:
		_index = load_index()
		_b = (_index.get("branches", {})).get(branch) or {}
		_branch_snapshot_names = {c.get("snapshot", "") for c in (_b.get("commits", []) or []) if c.get("snapshot")}
	except Exception:
		_branch_snapshot_names = set()

	items: List[tuple[str, bpy.types.Collection]] = []
	for c in dot_coll.children:
		name = c.name or ""

		# Prefer explicit branch tag set on commit
		try:
			tag = c.get("gitblend_branch", None)
		except Exception:
			tag = None

		if tag is not None:
			if str(tag) != str(branch):
				continue
			m = _UID_RE.search(name)
			if not m:
				continue
			uid = m.group(1)
			if max_uid is not None and uid > max_uid:
				continue
			items.append((uid, c))
			continue

		# Fallback: prefer exact names known from index; else parse base safely
		if name in _branch_snapshot_names:
			m = _UID_RE.search(name)
			if not m:
				continue
			uid = m.group(1)
			if max_uid is not None and uid > max_uid:
				continue
			items.append((uid, c))
			continue

		# Parse the name safely avoiding prefix collisions (best-effort)
		m = _UID_RE.search(name)
		if not m:
			continue
		base = name[: m.start()]
		uid = m.group(1)
		if not (base == branch or base.startswith(f"{branch}-")):
			continue
		if max_uid is not None and uid > max_uid:
			continue
		items.append((uid, c))

	# Sort by UID descending (newest first)
	items.sort(key=lambda t: t[0], reverse=True)
	return [c for _, c in items]


def ensure_mirrored_collection_path(source_coll: bpy.types.Collection,
									snapshot_path: List[bpy.types.Collection]) -> bpy.types.Collection:
	"""Ensure a mirrored collection path exists under source collection.

	Creates nested collections as needed to mirror the structure from the snapshot.

	Args:
		source_coll: Root collection to create structure under
		snapshot_path: Path of collections from snapshot (first is root, rest are children)

	Returns:
		The final collection in the mirrored path
	"""
	dest = source_coll
	# Skip the first item in path as it's the root
	for snap_coll in snapshot_path[1:]:
		name = extract_original_name(snap_coll)

		# Look for existing child with this name
		existing = None
		for child in dest.children:
			if child.name == name:
				existing = child
				break

		if existing is None:
			try:
				new_coll = bpy.data.collections.new(name)
				dest.children.link(new_coll)
				dest = new_coll
			except Exception:
				# If creation fails, fallback to current dest
				break
		else:
			dest = existing

	return dest


def get_dotgitblend_collection(scene: bpy.types.Scene) -> Optional[bpy.types.Collection]:
	"""Get the .gitblend collection if it exists."""
	for c in scene.collection.children:
		if c.name == ".gitblend":
			return c
	return None


def copy_object_with_data(obj: bpy.types.Object, new_name_suffix: str = "") -> bpy.types.Object:
	"""Copy an object including its data, with optional name suffix."""
	dup = obj.copy()

	# Copy data if it exists
	if getattr(obj, "data", None) is not None:
		try:
			dup.data = obj.data.copy()
		except Exception:
			pass

	# Set new name if suffix provided
	if new_name_suffix:
		try:
			dup.name = f"{obj.name}_{new_name_suffix}"
		except Exception:
			pass

	# Store original name metadata
	try:
		dup["gitblend_orig_name"] = obj.name
	except Exception:
		pass

	return dup


def unlink_and_remove_object(obj: bpy.types.Object) -> bool:
	"""Safely unlink and remove an object from all collections and data.

	Returns:
		True if successful, False if there was an error
	"""
	try:
		# Unlink from all collections
		for col in list(obj.users_collection):
			try:
				col.objects.unlink(obj)
			except Exception:
				pass

		# Remove from data
		bpy.data.objects.remove(obj, do_unlink=True)
		return True
	except Exception:
		return False


def set_object_parent_safely(child: bpy.types.Object, parent: Optional[bpy.types.Object]) -> bool:
	"""Safely set object parent relationship.

	Returns:
		True if successful, False if there was an error
	"""
	try:
		child.parent = parent
		return True
	except Exception:
		return False

def exclude_collection_in_all_view_layers(scene: bpy.types.Scene, coll: bpy.types.Collection) -> None:
	"""Exclude the given collection in all scene view layers."""
	def find_layer_collection(layer_coll, target_coll):
		if layer_coll.collection == target_coll:
			return layer_coll
		for child in layer_coll.children:
			found = find_layer_collection(child, target_coll)
			if found:
				return found
		return None

	for vl in scene.view_layers:
		lc = find_layer_collection(vl.layer_collection, coll)
		if lc:
			lc.exclude = True
def _get_or_create_gitblend_scene() -> bpy.types.Scene:
	"""Find or create a dedicated 'gitblend' Scene to hold snapshots (visible in UI).

	Migration: if a legacy scene named '.gitblend' exists and 'gitblend' does not,
	rename the legacy scene to 'gitblend'.
	"""
	# Prefer visible name without dot
	scene_name = SCENE_DIR
	s = bpy.data.scenes.get(scene_name)
	if s:
		return s
	# Migrate legacy hidden scene name
	legacy = bpy.data.scenes.get(HIDDEN_SCENE_DIR)
	if legacy and bpy.data.scenes.get(scene_name) is None:
		try:
			legacy.name = scene_name
			return legacy
		except Exception:
			pass
	# Create a new scene; do not switch context here
	try:
		s = bpy.data.scenes.new(scene_name)
	except Exception:
		# Fallback: attempt a different unique name
		base = SCENE_DIR
		i = 1
		while bpy.data.scenes.get(f"{base}-{i}") is not None:
			i += 1
		s = bpy.data.scenes.new(f"{base}-{i}")
	return s


def ensure_gitblend_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
	"""Return the root collection of the 'gitblend' Scene (creates the Scene if missing)."""
	dot_scene = _get_or_create_gitblend_scene()
	return dot_scene.collection

def slugify(text: str, max_len: int = 50) -> str:
	s = (text or "").strip().lower()
	s = "".join(ch if ch.isalnum() else '-' for ch in s)
	s = re.sub(r'-+', '-', s).strip('-')
	return s[:max_len] if s else ""


def unique_coll_name(base: str, uid: str) -> str:
	candidate = f"{base}_{uid}"
	if bpy.data.collections.get(candidate) is None:
		return candidate
	i = 1
	while bpy.data.collections.get(f"{candidate}-{i}") is not None:
		i += 1
	return f"{candidate}-{i}"


def unique_obj_name(base: str, uid: str) -> str:
	base_uid = f"{base}_{uid}"
	if bpy.data.objects.get(base_uid) is None:
		return base_uid
	i = 1
	while bpy.data.objects.get(f"{base_uid}-{i}") is not None:
		i += 1
	return f"{base_uid}-{i}"


def duplicate_collection_hierarchy(src: bpy.types.Collection, parent: bpy.types.Collection, uid: str,
								   obj_map: dict[bpy.types.Object, bpy.types.Object] | None = None) -> bpy.types.Collection:
	"""Duplicate a collection tree under parent. Returns the new collection. Populates obj_map if provided."""

	if obj_map is None:
		obj_map = {}
	new_name = unique_coll_name(src.name, uid)
	new_coll = bpy.data.collections.new(new_name)
	parent.children.link(new_coll)
	# store metadata for easier matching later
	try:
		new_coll["gitblend_uid"] = uid
		new_coll["gitblend_orig_name"] = src.name
	except Exception:
		pass

	for obj in src.objects:
		dup = duplicate_object_with_data(obj)
		dup.name = unique_obj_name(obj.name, uid)
		new_coll.objects.link(dup)
		# store original name for robust comparisons
		try:
			dup["gitblend_orig_name"] = obj.name
		except Exception:
			pass
		obj_map[obj] = dup

	for child in src.children:
		duplicate_collection_hierarchy(child, new_coll, uid, obj_map)

	return new_coll


def remap_parenting(obj_map: dict[bpy.types.Object, bpy.types.Object]) -> None:
	"""DEPRECATED: No longer used; parenting is handled during diff snapshot creation."""
	for _orig, _dup in list(obj_map.items()):
		# Intentionally no-op
		pass

##############################################
# Change validation helpers and API
##############################################

# Remove duplicated utility functions - now using shared ones from collection_ops

def _base_name_from_snapshot(name: str) -> str:
    """Remove trailing _<uid>[-i] suffix from names created by unique_* helpers."""
    m = _UID_RE.search(name or "")
    if m:
        return name[: m.start()]
    return name


def _list_branch_snapshots(scene: bpy.types.Scene, branch: str) -> List[bpy.types.Collection]:
	"""All snapshot collections in the 'gitblend' Scene for a given branch.
	Matches names starting with 'branch' (with or without '-<slug>') and ending with '_<uid>'.
	Sorted by UID descending.
	"""
	dot_scene = bpy.data.scenes.get(SCENE_DIR) or bpy.data.scenes.get(HIDDEN_SCENE_DIR)
	if not dot_scene:
		return []
	dot_root = dot_scene.collection

	items: List[Tuple[str, bpy.types.Collection]] = []
	for c in dot_root.children:
		nm = c.name or ""
		if not nm.startswith(branch):
			continue
		m = _UID_RE.search(nm)
		uid = m.group(1) if m else ""
		if not uid:
			continue
		items.append((uid, c))

	items.sort(key=lambda t: t[0], reverse=True)
	return [c for _, c in items]


def list_branch_snapshots_upto_uid(scene: bpy.types.Scene, branch: str, max_uid: str) -> List[bpy.types.Collection]:
    """Get branch snapshots up to and including the specified UID."""
    all_snapshots = _list_branch_snapshots(scene, branch)
    return [s for uid, s in [((_UID_RE.search(s.name or "").group(1) if _UID_RE.search(s.name or "") else ""), s) 
                              for s in all_snapshots] if uid and uid <= max_uid]


def get_latest_snapshot(scene: bpy.types.Scene, branch: str) -> Optional[bpy.types.Collection]:
	snapshots = list_branch_snapshots(scene, branch)
	return snapshots[0] if snapshots else None


def _floats_eq(a: float, b: float, eps: float = EPS) -> bool:
	return isclose(a, b, rel_tol=0.0, abs_tol=eps)


def _vecs_eq(a, b, eps: float = EPS) -> bool:
	try:
		return all(_floats_eq(float(x), float(y), eps) for x, y in zip(a, b))
	except Exception:
		return False


def _matrices_eq(m1, m2, eps: float = EPS) -> bool:
	try:
		for i in range(4):
			for j in range(4):
				if not _floats_eq(float(m1[i][j]), float(m2[i][j]), eps):
					return False
		return True
	except Exception:
		return False


def _compare_transforms(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	# Compare world matrices first (covers loc/rot/scale in one)
	if not _matrices_eq(a.matrix_world, b.matrix_world, EPS):
		return "transform differs (matrix_world)"
	# Origin position (world translation)
	if not _vecs_eq(a.matrix_world.translation, b.matrix_world.translation, EPS):
		return "origin position differs"
	return None


def _compare_dimensions(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	if not _vecs_eq(a.dimensions, b.dimensions, EPS):
		return "bounding box dimensions differ"
	return None


def _obj_is_mesh(o: bpy.types.Object) -> bool:
	return getattr(o, "type", None) == "MESH" and getattr(o, "data", None) is not None


def _compare_vertex_count(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	if not (_obj_is_mesh(a) and _obj_is_mesh(b)):
		return None
	if len(a.data.vertices) != len(b.data.vertices):
		return "vertex count differs"
	return None


def _compare_modifiers(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	ma = [(m.type, m.name) for m in getattr(a, "modifiers", [])]
	mb = [(m.type, m.name) for m in getattr(b, "modifiers", [])]
	if ma != mb:
		return "modifiers differ (stack/type/name)"
	return None


def _hash_modifier_settings(m) -> str:
	"""Stable summary hash of a modifier's settings (subset of RNA props)."""
	try:
		def _serialize_val(v):
			try:
				if isinstance(v, float):
					return f"{v:.6f}"
				if isinstance(v, (list, tuple)):
					parts = []
					for x in v:
						if isinstance(x, float):
							parts.append(f"{float(x):.6f}")
						else:
							parts.append(str(x))
					return "(" + ",".join(parts) + ")"
				return str(v)
			except Exception:
				return ""

		parts: List[str] = []
		SKIP = {"name", "type", "rna_type", "bl_rna"}
		for p in m.bl_rna.properties:  # type: ignore[attr-defined]
			try:
				pid = getattr(p, "identifier", "")
			except Exception:
				pid = ""
			if not pid or pid in SKIP:
				continue
			try:
				if getattr(p, "is_hidden", False) or getattr(p, "is_readonly", False):
					continue
			except Exception:
				pass
			try:
				ptype = getattr(p, "type", None)
			except Exception:
				ptype = None
			if ptype in {"POINTER", "COLLECTION"}:
				if pid == "node_group":
					try:
						ng = getattr(m, "node_group", None)
						parts.append(f"node_group:{getattr(ng, 'name', '') if ng else ''}")
					except Exception:
						pass
				continue
			try:
				val = getattr(m, pid)
			except Exception:
				continue
			if callable(val):
				continue
			try:
				if hasattr(val, "__len__") and not isinstance(val, (str, bytes)):
					try:
						seq = [val[i] for i in range(len(val))]
					except Exception:
						seq = None
					if seq is not None and len(seq) <= 16:
						parts.append(f"{pid}:{_serialize_val(seq)}")
						continue
			except Exception:
				pass
			parts.append(f"{pid}:{_serialize_val(val)}")
		parts_sorted = sorted(parts)
		import hashlib
		return hashlib.sha256("|".join(parts_sorted).encode("utf-8", errors="ignore")).hexdigest()
	except Exception:
		return ""


def _compare_modifiers_settings(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	ma = [(m.type, m.name, _hash_modifier_settings(m)) for m in getattr(a, "modifiers", [])]
	mb = [(m.type, m.name, _hash_modifier_settings(m)) for m in getattr(b, "modifiers", [])]
	if len(ma) != len(mb):
		return None  # stack/name/type difference is handled by _compare_modifiers
	for (ta, na, ha), (tb, nb, hb) in zip(ma, mb):
		if ta != tb or na != nb:
			return None  # defer to _compare_modifiers for this difference
		if ha != hb:
			return f"modifier settings differ ({na})"
	return None


def _compare_vertex_groups(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	# Compare group names only here (cheap); detailed weights later
	na = {g.name for g in getattr(a, "vertex_groups", [])}
	nb = {g.name for g in getattr(b, "vertex_groups", [])}
	if na != nb:
		return "vertex groups differ (names)"
	return None


def _compare_uv_layers_meta(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	if not (_obj_is_mesh(a) and _obj_is_mesh(b)):
		return None
	la = getattr(a.data, "uv_layers", None)
	lb = getattr(b.data, "uv_layers", None)
	ca = len(la) if la else 0
	cb = len(lb) if lb else 0
	if ca != cb:
		return "uv layers count differs"
	names_a = [uv.name for uv in la] if la else []
	names_b = [uv.name for uv in lb] if lb else []
	if names_a != names_b:
		return "uv layer names differ"
	return None


def _compare_shapekeys_meta(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	ka = getattr(getattr(a.data, "shape_keys", None), "key_blocks", None)
	kb = getattr(getattr(b.data, "shape_keys", None), "key_blocks", None)
	ca = len(ka) if ka else 0
	cb = len(kb) if kb else 0
	if ca != cb:
		return "shapekeys count differs"
	if ka and kb:
		names_a = [k.name for k in ka]
		names_b = [k.name for k in kb]
		if names_a != names_b:
			return "shapekey names differ"
	return None


def _compare_uv_data(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	if not (_obj_is_mesh(a) and _obj_is_mesh(b)):
		return None
	la = getattr(a.data, "uv_layers", None)
	lb = getattr(b.data, "uv_layers", None)
	if not la and not lb:
		return None
	if not la or not lb:
		return "uv data presence differs"
	for i, (uva, uvb) in enumerate(zip(la, lb)):
		da = uva.data
		db = uvb.data
		if len(da) != len(db):
			return f"uv data length differs (layer {i})"
		for j, (pa, pb) in enumerate(zip(da, db)):
			# Compare loop UV coordinates
			if not (_floats_eq(pa.uv.x, pb.uv.x, EPS) and _floats_eq(pa.uv.y, pb.uv.y, EPS)):
				return f"uv coords differ (layer {i}, loop {j})"
	return None


def _compare_shapekeys_data(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	ka = getattr(getattr(a.data, "shape_keys", None), "key_blocks", None)
	kb = getattr(getattr(b.data, "shape_keys", None), "key_blocks", None)
	if not ka and not kb:
		return None
	if not ka or not kb:
		return "shapekey presence differs"
	for i, (ka_i, kb_i) in enumerate(zip(ka, kb)):
		if not _floats_eq(float(ka_i.value), float(kb_i.value), EPS):
			return f"shapekey values differ ({ka_i.name})"
		# Compare coordinates length (heavy to compare all points, so defer)
		if len(ka_i.data) != len(kb_i.data):
			return f"shapekey point counts differ ({ka_i.name})"
	return None


def _compare_shapekey_points(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	ka = getattr(getattr(a.data, "shape_keys", None), "key_blocks", None)
	kb = getattr(getattr(b.data, "shape_keys", None), "key_blocks", None)
	if not ka and not kb:
		return None
	if not ka or not kb:
		return "shapekey presence differs (points phase)"
	for i, (ka_i, kb_i) in enumerate(zip(ka, kb)):
		# Skip Basis to save time; changes usually exist in other keys
		if (ka_i.name or "").lower() == "basis":
			continue
		da = ka_i.data
		db = kb_i.data
		if len(da) != len(db):
			return f"shapekey point counts differ ({ka_i.name})"
		for vi, (pa, pb) in enumerate(zip(da, db)):
			if not _vecs_eq(pa.co, pb.co, EPS):
				return f"shapekey '{ka_i.name}' point differs at v{vi}"
	return None


def _compare_vertex_weights(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	# Build name->index maps
	ga = {g.index: g.name for g in getattr(a, "vertex_groups", [])}
	gb = {g.index: g.name for g in getattr(b, "vertex_groups", [])}
	# Quickly exit if names differ already handled; continue only on overlap
	if not ga and not gb:
		return None
	if len(a.data.vertices) != len(b.data.vertices):
		return "vertex count differs (weights phase)"
	va = a.data.vertices
	vb = b.data.vertices
	for idx in range(len(va)):
		# Create name->weight dicts per vertex
		da = {ga[g.group]: g.weight for g in va[idx].groups if g.group in ga}
		db = {gb[g.group]: g.weight for g in vb[idx].groups if g.group in gb}
		if da.keys() != db.keys():
			return f"vertex group membership differs at v{idx}"
		for k in da.keys():
			if not _floats_eq(float(da[k]), float(db[k]), EPS):
				return f"vertex weight differs for group '{k}' at v{idx}"
	return None


def _compare_vertex_world_positions(a: bpy.types.Object, b: bpy.types.Object) -> Optional[str]:
	if not (_obj_is_mesh(a) and _obj_is_mesh(b)):
		return None
	if len(a.data.vertices) != len(b.data.vertices):
		return "vertex count differs (positions phase)"
	ma = a.matrix_world
	mb = b.matrix_world
	va = a.data.vertices
	vb = b.data.vertices
	for i in range(len(va)):
		pa = ma @ va[i].co
		pb = mb @ vb[i].co
		if not _vecs_eq(pa, pb, EPS_POS):
			return f"vertex world position differs at index {i}"
	return None


def collections_identical(curr: bpy.types.Collection, prev: bpy.types.Collection, subset_mode: bool = False) -> Tuple[bool, str]:
	"""Compare two collections (current working vs previous snapshot) with early exits.
	Returns (is_identical, reason). On difference, reason describes the first detected mismatch.
	If subset_mode=True, only compare objects that exist in 'prev' (useful when 'prev' is a differential snapshot).
	Order of checks: names -> transforms -> dimensions -> vert count -> modifiers -> vgroup names -> UV meta -> shapekey meta -> UV data -> weights -> vertex world positions.
	"""
	curr_map = build_name_map(curr, snapshot=False)
	prev_map = build_name_map(prev, snapshot=True)

	if not curr_map and not prev_map:
		return True, "both empty"

	names_curr: Set[str] = set(curr_map.keys())
	names_prev: Set[str] = set(prev_map.keys())

	if not subset_mode:
		# Strict equality of name sets
		if names_curr != names_prev:
			missing = names_prev - names_curr
			added = names_curr - names_prev
			if missing:
				return False, f"names missing in current: {sorted(list(missing))[:3]}"
			else:
				return False, f"new names in current: {sorted(list(added))[:3]}"
		names_to_check = sorted(names_curr)
	else:
		# Only ensure all prev names still exist; extra current names are ignored
		if not names_prev.issubset(names_curr):
			missing = names_prev - names_curr
			return False, f"names missing in current (subset): {sorted(list(missing))[:3]}"
		names_to_check = sorted(names_prev)

	# For each matching name, run ordered checks with early exit
	for name in names_to_check:
		a = curr_map[name]
		b = prev_map[name]
		for check in (
			_compare_transforms,
			_compare_dimensions,
			_compare_vertex_count,
			_compare_modifiers,
			_compare_modifiers_settings,
			_compare_vertex_groups,
			_compare_uv_layers_meta,
			_compare_shapekeys_meta,
			_compare_uv_data,
			_compare_shapekeys_data,
			_compare_vertex_weights,
			_compare_vertex_world_positions,
			_compare_shapekey_points,
		):
			reason = check(a, b)
			if reason:
				return False, f"{name}: {reason}"

	return True, "identical"


def commit_contains_previous_names(curr: bpy.types.Collection, prev: bpy.types.Collection) -> bool:
	"""Cheap pre-check: does current contain all names that existed previously?"""
	curr_map = build_name_map(curr, snapshot=False)
	prev_map = build_name_map(prev, snapshot=True)
	return set(prev_map.keys()).issubset(set(curr_map.keys()))


def should_skip_commit(scene: bpy.types.Scene, curr: bpy.types.Collection, branch: str) -> Tuple[bool, str]:
	"""Return (skip, reason).
	Preferred fast path: compare current collection hash with the last commit's stored hash.
	Fallback: compare against the latest on-disk snapshot in .gitblend.
	"""
	# CAS-based detection (preferred): compare against last commit object set.
	index_reports_unchanged = False
	try:
		latest = get_latest_commit_objects(branch)
		if latest:
			_cid, _commit, prev_objs = latest
			curr_sigs, _curr_hash = compute_collection_signature(curr)
			changed, _names = derive_changed_set(curr_sigs, prev_objs)
			index_reports_unchanged = not changed
	except Exception:
		index_reports_unchanged = False

	# Fallback to snapshot-based comparison
	prev = get_latest_snapshot(scene, branch)
	if not prev:
		# Without a snapshot to compare, only rely on index; skip only if index says unchanged
		return (index_reports_unchanged, "index unchanged (no previous snapshot)" if index_reports_unchanged else "no previous snapshot")
	# Cheapest: ensure current still contains previous names
	if not commit_contains_previous_names(curr, prev):
		return False, "name sets differ"
	# Full comparison (ordered with early exit)
	same, reason = collections_identical(curr, prev, subset_mode=True)
	# Be conservative: require both index and snapshot to report unchanged to skip
	if index_reports_unchanged and same:
		return True, f"index+snapshot unchanged ({reason})"
	return False, "changes detected"


##############################################
# Differential snapshot creation
##############################################

def objects_identical(a: bpy.types.Object, b: bpy.types.Object) -> Tuple[bool, str]:
	for check in (
		_compare_transforms,
		_compare_dimensions,
		_compare_vertex_count,
		_compare_modifiers,
		_compare_modifiers_settings,
		_compare_vertex_groups,
		_compare_uv_layers_meta,
		_compare_shapekeys_meta,
		_compare_uv_data,
		_compare_shapekeys_data,
		_compare_vertex_weights,
		_compare_vertex_world_positions,
		_compare_shapekey_points,
	):
		reason = check(a, b)
		if reason:
			return False, reason
	return True, "identical"


def _new_snapshot_collection_for(src: bpy.types.Collection, parent: bpy.types.Collection, uid: str) -> bpy.types.Collection:
	new_name = unique_coll_name(src.name, uid)
	new_coll = bpy.data.collections.new(new_name)
	parent.children.link(new_coll)
	try:
		new_coll["gitblend_uid"] = uid
		new_coll["gitblend_orig_name"] = src.name
	except Exception:
		pass
	return new_coll


def _duplicate_collection_hierarchy_diff_recursive(
	src: bpy.types.Collection,
	new_parent: bpy.types.Collection,
	uid: str,
	name_to_new_obj: Dict[str, bpy.types.Object],
	copied_names: Set[str],
	changed: Set[str],
) -> Optional[bpy.types.Collection]:
	"""Create a new snapshot collection node for src under new_parent, copying only changed objects.
	Pure-delta: unchanged objects are omitted. Populates name_to_new_obj with newly copied objects by original name.
	copied_names records which original names were duplicated (to fix parenting later).
	"""
	def _subtree_has_changes(coll: bpy.types.Collection) -> bool:
		for o in iter_objects_recursive(coll):
			if (o.name or "") in changed:
				return True
		return False

	if not _subtree_has_changes(src):
		return None

	new_coll = _new_snapshot_collection_for(src, new_parent, uid)

	# Place only changed objects for this collection
	for obj in src.objects:
		name = obj.name
		if not name:
			continue
		if name not in changed:
			continue
		dup = duplicate_object_with_data(obj)
		dup.name = unique_obj_name(obj.name, uid)
		new_coll.objects.link(dup)
		try:
			dup["gitblend_orig_name"] = obj.name
		except Exception:
			pass
		name_to_new_obj[name] = dup
		copied_names.add(name)

	# Recurse into children collections (only those with changes will create nodes)
	for child in src.children:
		_duplicate_collection_hierarchy_diff_recursive(child, new_coll, uid, name_to_new_obj, copied_names, changed)

	return new_coll


def create_diff_snapshot(
	src: bpy.types.Collection,
	parent_dot: bpy.types.Collection,
	uid: str,
) -> Tuple[bpy.types.Collection, Dict[str, bpy.types.Object]]:
	"""Backward-compatible wrapper: no previous snapshot or changed set provided."""
	return _create_diff_snapshot_internal(src, parent_dot, uid, prev_snapshot=None, changed_names=None)


def create_diff_snapshot_with_changes(
	src: bpy.types.Collection,
	parent_dot: bpy.types.Collection,
	uid: str,
	prev_snapshot: Optional[bpy.types.Collection],
	changed_names: Optional[Set[str]] = None,
) -> Tuple[bpy.types.Collection, Dict[str, bpy.types.Object]]:
	"""Create a new snapshot collection that contains only differences from prev_snapshot.
	If changed_names is provided, use it directly (plus descendant propagation) instead of recomputing.
	Returns the new collection and a map of original-name -> object in new snapshot.
	"""
	return _create_diff_snapshot_internal(src, parent_dot, uid, prev_snapshot=prev_snapshot, changed_names=changed_names)


def _create_diff_snapshot_internal(
	src: bpy.types.Collection,
	parent_dot: bpy.types.Collection,
	uid: str,
	prev_snapshot: Optional[bpy.types.Collection],
	changed_names: Optional[Set[str]] = None,
) -> Tuple[bpy.types.Collection, Dict[str, bpy.types.Object]]:
	"""Internal helper to support both legacy and explicit-changes flows."""
	prev_map: Dict[str, bpy.types.Object] = {}

	curr_objs: Dict[str, bpy.types.Object] = {}
	parent_of: Dict[str, Optional[str]] = {}
	for o in iter_objects_recursive(src):
		nm = o.name or ""
		if not nm:
			continue
		curr_objs[nm] = o
		parent_of[nm] = o.parent.name if o.parent else None

	changed: Set[str] = set(changed_names or [])
	if not changed:
		if prev_snapshot is not None:
			prev_map = build_name_map(prev_snapshot, snapshot=True)
		for nm, o in curr_objs.items():
			prev_o = prev_map.get(nm)
			if prev_o is None:
				changed.add(nm)
				continue
			same, _ = objects_identical(o, prev_o)
			if not same:
				changed.add(nm)

	# Simple dependency expansion: include objects that changed objects depend on
	expanded_changed = set(changed)
	for obj_name in list(changed):
		if obj_name in curr_objs:
			obj = curr_objs[obj_name]
			dependencies = get_object_dependencies(obj)
			# Add dependencies that exist in current objects
			for dep_name in dependencies:
				if dep_name in curr_objs:
					expanded_changed.add(dep_name)
	
	changed = expanded_changed

	# Propagate change to descendants: if a parent is changed, all its children change
	changed_stable = False
	while not changed_stable:
		before = len(changed)
		for nm, parent_nm in list(parent_of.items()):
			if parent_nm and parent_nm in changed and nm not in changed:
				changed.add(nm)
		changed_stable = len(changed) == before

	name_to_new_obj: Dict[str, bpy.types.Object] = {}
	copied_names: Set[str] = set()
	new_coll = _new_snapshot_collection_for(src, parent_dot, uid)

	# Copy only changed objects at root level
	for obj in src.objects:
		name = obj.name or ""
		if not name or name not in changed:
			continue
		dup = duplicate_object_with_data(obj)
		dup.name = unique_obj_name(obj.name, uid)
		new_coll.objects.link(dup)
		try:
			dup["gitblend_orig_name"] = obj.name
		except Exception:
			pass
		name_to_new_obj[name] = dup
		copied_names.add(name)

	# Recurse into children collections; only create for subtrees with changes
	for child in src.children:
		_duplicate_collection_hierarchy_diff_recursive(child, new_coll, uid, name_to_new_obj, copied_names, changed)

	# Fix parenting for newly copied objects only; linked ones already refer to linked parents (unchanged case)
	for nm in copied_names:
		dup = name_to_new_obj.get(nm)
		if not dup:
			continue
		src_obj = curr_objs.get(nm)
		if src_obj and src_obj.parent:
			p_name = src_obj.parent.name
			target_parent = name_to_new_obj.get(p_name)
			if target_parent:
				try:
					dup.parent = target_parent
				except Exception:
					pass

	# Remap pointers INSIDE the snapshot duplicates to point to duplicated targets (manual-copy behavior)
	try:
		# Fallback resolver map: current source objects by original name
		existing_by_name = {nm: obj for nm, obj in curr_objs.items()}
		remap_references_for_objects(name_to_new_obj, existing_by_name)
	except Exception:
		pass

	return new_coll, name_to_new_obj
