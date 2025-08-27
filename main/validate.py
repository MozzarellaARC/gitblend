import bpy
import re
from math import isclose
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Tolerances for float comparisons
EPS = 1e-6
EPS_POS = 1e-5  # slightly looser for world positions

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
		dup = obj.copy()
		if getattr(obj, "data", None) is not None:
			try:
				dup.data = obj.data.copy()
			except Exception:
				pass
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


def _orig_name(id_block) -> Optional[str]:
	try:
		v = id_block.get("gitblend_orig_name", None)
		if isinstance(v, str) and v:
			return v
	except Exception:
		pass
	# Fallback to strip UID suffix
	return _base_name_from_snapshot(getattr(id_block, "name", ""))


def _iter_objects_recursive(coll: bpy.types.Collection) -> Iterable[bpy.types.Object]:
	for o in coll.objects:
		yield o
	for c in coll.children:
		yield from _iter_objects_recursive(c)


def _build_name_map_for_collection(coll: bpy.types.Collection, snapshot: bool) -> Dict[str, bpy.types.Object]:
	"""Map base/original names to objects, recursively.
	If snapshot=True, use stored gitblend_orig_name when available.
	For duplicates, later entries won't overwrite earlier ones to keep first occurrence.
	"""
	out: Dict[str, bpy.types.Object] = {}
	for obj in _iter_objects_recursive(coll):
		name = _orig_name(obj) if snapshot else (obj.name or "")
		if not name:
			continue
		if name not in out:
			out[name] = obj
	return out


def _list_branch_snapshots(scene: bpy.types.Scene, branch: str) -> List[bpy.types.Collection]:
	"""All snapshot collections in .gitblend for a given branch (prefix match 'branch-'). Sorted by UID descending."""
	root = scene.collection
	dot = None
	for c in root.children:
		if c.name == ".gitblend":
			dot = c
			break
	if not dot:
		return []

	pref = f"{branch}-"
	items: List[Tuple[str, bpy.types.Collection]] = []
	for c in dot.children:
		nm = c.name or ""
		if not nm.startswith(pref):
			continue
		m = _UID_RE.search(nm)
		uid = m.group(1) if m else ""
		items.append((uid, c))

	# Sort newest first (string uid is sortable as datetime-like yyyymmdd...)
	items.sort(key=lambda t: t[0], reverse=True)
	return [c for _, c in items]


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


def collections_identical(curr: bpy.types.Collection, prev: bpy.types.Collection) -> Tuple[bool, str]:
	"""Compare two collections (current working vs previous snapshot) with early exits.
	Returns (is_identical, reason). On difference, reason describes the first detected mismatch.
	Order of checks: names -> transforms -> dimensions -> vert count -> modifiers -> vgroup names -> UV meta -> shapekey meta -> UV data -> weights -> vertex world positions.
	"""
	curr_map = _build_name_map_for_collection(curr, snapshot=False)
	prev_map = _build_name_map_for_collection(prev, snapshot=True)

	if not curr_map and not prev_map:
		return True, "both empty"

	# Quick name set comparison
	names_curr: Set[str] = set(curr_map.keys())
	names_prev: Set[str] = set(prev_map.keys())
	if names_curr != names_prev:
		missing = names_prev - names_curr
		added = names_curr - names_prev
		if missing:
			return False, f"names missing in current: {sorted(list(missing))[:3]}"
		else:
			return False, f"new names in current: {sorted(list(added))[:3]}"

	# For each matching name, run ordered checks with early exit
	for name in sorted(names_curr):
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
			reason = check(a, b) if check in {_compare_vertex_count, _compare_modifiers, _compare_vertex_groups,
											 _compare_uv_layers_meta, _compare_shapekeys_meta,
											 _compare_uv_data, _compare_shapekeys_data,
											 _compare_vertex_weights, _compare_vertex_world_positions} else check(a, b)
			if reason:
				return False, f"{name}: {reason}"

	return True, "identical"


def commit_contains_previous_names(curr: bpy.types.Collection, prev: bpy.types.Collection) -> bool:
	"""Cheap pre-check: does current contain all names that existed previously?"""
	curr_map = _build_name_map_for_collection(curr, snapshot=False)
	prev_map = _build_name_map_for_collection(prev, snapshot=True)
	return set(prev_map.keys()).issubset(set(curr_map.keys()))


def should_skip_commit(scene: bpy.types.Scene, curr: bpy.types.Collection, branch: str) -> Tuple[bool, str]:
	"""Return (skip, reason). Skip when there is a previous snapshot for the branch and collections are identical."""
	prev = get_latest_snapshot(scene, branch)
	if not prev:
		return False, "no previous snapshot"
	# Cheapest: ensure current still contains previous names
	if not commit_contains_previous_names(curr, prev):
		return False, "name sets differ"
	# Full comparison (ordered with early exit)
	same, reason = collections_identical(curr, prev)
	return (same, reason)