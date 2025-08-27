import bpy
import re








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

	for obj in src.objects:
		dup = obj.copy()
		if getattr(obj, "data", None) is not None:
			try:
				dup.data = obj.data.copy()
			except Exception:
				pass
		dup.name = unique_obj_name(obj.name, uid)
		new_coll.objects.link(dup)
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