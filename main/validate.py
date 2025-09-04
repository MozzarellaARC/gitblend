import bpy
import re
import json
import hashlib
from math import isclose
from typing import Dict, Iterable, List, Optional, Set, Tuple
from .utils import (
    iter_objects_recursive,
    build_name_map,
    duplicate_object_with_data,
	remap_references_for_objects,
	compute_pointer_dependency_closure,
)

# Tolerances for float comparisons (relaxed slightly to avoid noise-based false positives)
EPS = 1e-5
EPS_POS = 5e-4  # looser for world positions

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

def ensure_gitblend_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
	"""Find or create the hidden .gitblend collection under the scene root."""
	root = scene.collection
	for c in root.children:
		if c.name == ".gitblend":
			return c
	coll = bpy.data.collections.new(".gitblend")
	root.children.link(coll)
	exclude_collection_in_all_view_layers(scene, coll)
	return coll

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
	for orig, dup in list(obj_map.items()):
		if orig.parent and orig.parent in obj_map:
			try:
				dup.parent = obj_map[orig.parent]
			except Exception:
				pass

##############################################
# Change validation helpers and API
##############################################

_UID_RE = re.compile(r"_(\d{10,20})(?:-\d+)?$")


def _base_name_from_snapshot(name: str) -> str:
    """Remove trailing _<uid>[-i] suffix from names created by unique_* helpers."""
    m = _UID_RE.search(name or "")
    if m:
        return name[: m.start()]
    return name


def _list_branch_snapshots(scene: bpy.types.Scene, branch: str) -> List[bpy.types.Collection]:
    """All snapshot collections in .gitblend for a given branch.
    Matches names starting with 'branch' (with or without '-<slug>') and ending with '_<uid>'.
    Sorted by UID descending.
    """
    root = scene.collection
    dot = None
    for c in root.children:
        if c.name == ".gitblend":
            dot = c
            break
    if not dot:
        return []

    items: List[Tuple[str, bpy.types.Collection]] = []
    for c in dot.children:
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
	lst = _list_branch_snapshots(scene, branch)
	return lst[0] if lst else None


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
	Snapshot-based comparison only: compare current collection to the latest on-disk snapshot in .gitblend.
	"""
	prev = get_latest_snapshot(scene, branch)
	if not prev:
		return False, "no previous snapshot"
	# Cheapest: ensure current still contains previous names
	if not commit_contains_previous_names(curr, prev):
		return False, "name sets differ"
	# Full comparison (ordered with early exit)
	same, reason = collections_identical(curr, prev, subset_mode=True)
	if same:
		return True, f"snapshot unchanged ({reason})"
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

	# Dependency closure via utility (includes external tracking)
	changed, external_deps = compute_pointer_dependency_closure(curr_objs, changed)

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

	# Include external dependency objects directly under the snapshot root (best-effort)
	if external_deps:
		for dep_name in sorted(external_deps):
			try:
				if dep_name in name_to_new_obj:
					continue
				dep_obj = bpy.data.objects.get(dep_name)
				if not dep_obj:
					continue
				dup = duplicate_object_with_data(dep_obj)
				dup.name = unique_obj_name(dep_obj.name, uid)
				new_coll.objects.link(dup)
				try:
					dup["gitblend_orig_name"] = dep_obj.name
				except Exception:
					pass
				name_to_new_obj[dep_obj.name] = dup
				copied_names.add(dep_obj.name)
			except Exception:
				continue

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


##############################################
# Signatures and hashing (formerly in index.py)
##############################################

def _flatten_matrix_world(mw) -> list:
	try:
		return [float(mw[i][j]) for i in range(4) for j in range(4)]
	except Exception:
		return []


def _obj_signature(o: bpy.types.Object) -> Dict:
	sig: Dict = {"name": o.name or "", "type": getattr(o, "type", "")}
	try:
		sig["dimensions"] = [float(x) for x in getattr(o, "dimensions", [])]
	except Exception:
		sig["dimensions"] = []
	try:
		sig["matrix_world"] = _flatten_matrix_world(getattr(o, "matrix_world", None))
	except Exception:
		sig["matrix_world"] = []
	# Mesh specifics
	try:
		if getattr(o, "type", None) == "MESH" and getattr(o, "data", None) is not None:
			sig["vertex_count"] = int(len(o.data.vertices))
			try:
				sig["uv_layers"] = [uv.name for uv in getattr(o.data, "uv_layers", [])]
			except Exception:
				sig["uv_layers"] = []
			try:
				keys = getattr(getattr(o.data, "shape_keys", None), "key_blocks", None)
				sig["shapekeys"] = [k.name for k in keys] if keys else []
			except Exception:
				sig["shapekeys"] = []
		else:
			sig["vertex_count"] = 0
			sig["uv_layers"] = []
			sig["shapekeys"] = []
	except Exception:
		pass
	# Vertex groups
	try:
		sig["vertex_groups"] = sorted([g.name for g in getattr(o, "vertex_groups", [])])
	except Exception:
		sig["vertex_groups"] = []
	# Modifiers (type+name)
	try:
		sig["modifiers"] = [(m.type, m.name) for m in getattr(o, "modifiers", [])]
	except Exception:
		sig["modifiers"] = []
	# Parent name only
	try:
		sig["parent"] = o.parent.name if getattr(o, "parent", None) else None
	except Exception:
		sig["parent"] = None
	return sig


def compute_collection_signature(curr: bpy.types.Collection) -> Tuple[Dict[str, Dict], str]:
	"""Compute per-object signatures and a collection hash.

	Returns (obj_sigs, collection_hash) where obj_sigs maps object name to its signature dict.
	"""
	objs = build_name_map(curr, snapshot=False)
	obj_sigs: Dict[str, Dict] = {}
	for name, obj in sorted(objs.items()):
		try:
			obj_sigs[name] = _obj_signature(obj)
		except Exception:
			continue
	try:
		payload = json.dumps(obj_sigs, sort_keys=True, ensure_ascii=False)
		h = hashlib.sha1(payload.encode("utf-8")).hexdigest()
	except Exception:
		h = ""
	return obj_sigs, h