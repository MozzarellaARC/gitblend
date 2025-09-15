import bpy  # type: ignore
import random
import string
from typing import List, Optional

STASH_SCENE_NAME = "__gitblend_stash__"


def _ensure_stash_scene() -> bpy.types.Scene:
	"""Return the dedicated stash scene, creating it if needed.

	The stash scene is hidden from the user in typical workflows but stores
	object copies that the user has stashed. Objects placed here are safe
	until appended back into the active scene or deleted explicitly.
	"""
	scene = bpy.data.scenes.get(STASH_SCENE_NAME)
	if scene is None:
		scene = bpy.data.scenes.new(STASH_SCENE_NAME)
		# Try to mark as not visible in UI (Blender specifics; harmless if fails)
		try:
			scene.view_settings.view_transform = bpy.context.scene.view_settings.view_transform  # type: ignore
		except Exception:
			pass
	return scene


def _make_uid(prefix: str = "stash") -> str:
	rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
	return f"{prefix}_{rand}"


def _copy_objects_to_stash(objs: List[bpy.types.Object]) -> List[bpy.types.Object]:
	stash_scene = _ensure_stash_scene()
	new_objs = []
	for obj in objs:
		try:
			new_obj = obj.copy()
			if obj.data:
				try:
					new_obj.data = obj.data.copy()
				except Exception:
					pass
			new_obj.name = _make_uid(obj.name)
			stash_scene.collection.objects.link(new_obj)
			new_objs.append(new_obj)
		except Exception:
			continue
	return new_objs


def _list_stash_objects() -> List[bpy.types.Object]:
	scene = bpy.data.scenes.get(STASH_SCENE_NAME)
	if scene is None:
		return []
	return list(scene.objects)

def rebuild_stash_ui_collection(context: bpy.types.Context):
	"""Rebuild the stash_items collection on the scene properties.

	This must be invoked from operators (not from panel draw) because writing to
	ID properties during draw triggers Blender context write errors.
	"""
	props = getattr(context.scene, 'gitblend_props', None)
	if not props:
		return
	stash_objs = _list_stash_objects()

	def _parse(o_name: str):
		# Expect pattern like <prefix>_<maybeOriginal>_<random8> sometimes; we stored as prefix_random originally.
		# We'll try to separate original base and trailing 8-char uid.
		parts = o_name.split('_')
		uid = ''
		original = o_name
		if len(parts) >= 2 and len(parts[-1]) == 8 and parts[-1].isalnum():
			uid = parts[-1]
			original = '_'.join(parts[:-1])
		return original, uid

	# Build sortable tuples (original, uid, object)
	sortable = []
	for o in stash_objs:
		try:
			orig, uid = _parse(o.name)
			sortable.append((orig.lower(), uid.lower(), o, orig, uid))
		except Exception:
			continue
	# Sort by original then uid
	sortable.sort(key=lambda t: (t[0], t[1]))
	try:
		props.stash_items.clear()
		for _olow, _uidlow, o, orig, uid in sortable:
			entry = props.stash_items.add()
			entry.name = o.name
			entry.original = orig
			entry.uid = uid
		if props.stash_index >= len(props.stash_items):
			props.stash_index = len(props.stash_items) - 1
	except Exception:
		pass


def _post_stash_mutation(context: bpy.types.Context):
	"""Common actions after stash state changes.

	Rebuild UI collection and tag redraw. Wrapped to keep operator bodies concise
	and future-proof (e.g., if we add notifications or logging).
	"""
	try:
		rebuild_stash_ui_collection(context)
	except Exception:
		pass
	_tag_redraw()

class GITBLEND_OT_stash_add(bpy.types.Operator):
	bl_idname = "gitblend.stash_add"
	bl_label = "Stash Selected"
	bl_description = "Copy selected objects into the GitBlend stash scene"
	bl_options = {"REGISTER", "UNDO"}

	@classmethod
	def poll(cls, context):  # type: ignore
		return context.selected_objects and len(context.selected_objects) > 0

	def execute(self, context):
		objs = list(context.selected_objects)
		new_objs = _copy_objects_to_stash(objs)
		self.report({'INFO'}, f"Stashed {len(new_objs)} object(s)")
		_post_stash_mutation(context)
		return {'FINISHED'}


class GITBLEND_OT_stash_append(bpy.types.Operator):
	bl_idname = "gitblend.stash_append"
	bl_label = "Append From Stash"
	bl_description = "Append selected stash object(s) into the active scene"
	bl_options = {"REGISTER", "UNDO"}

	names: bpy.props.StringProperty(  # type: ignore
		name="Names",
		description="Comma separated stash object names to append",
		default=""
	)

	@classmethod
	def poll(cls, context):  # type: ignore
		return True

	def execute(self, context):
		target_scene = context.scene
		stash_objs = {o.name: o for o in _list_stash_objects()}
		requested = [n.strip() for n in self.names.split(',') if n.strip()]
		if not requested:
			self.report({'WARNING'}, "No stash object names provided")
			return {'CANCELLED'}
		appended = 0
		for name in requested:
			obj = stash_objs.get(name)
			if not obj:
				continue
			try:
				new_obj = obj.copy()
				if obj.data:
					try:
						new_obj.data = obj.data.copy()
					except Exception:
						pass
				new_obj.name = _make_uid("appended")
				target_scene.collection.objects.link(new_obj)
				appended += 1
			except Exception:
				continue
		self.report({'INFO'}, f"Appended {appended} object(s)")
		_post_stash_mutation(context)
		return {'FINISHED'}


class GITBLEND_OT_stash_refresh(bpy.types.Operator):
	bl_idname = "gitblend.stash_refresh"
	bl_label = "Refresh Stash List"
	bl_description = "Rebuild the stash object list UI"
	bl_options = {"INTERNAL"}

	@classmethod
	def poll(cls, context):  # type: ignore
		return True

	def execute(self, context):
		_post_stash_mutation(context)
		self.report({'INFO'}, "Stash list refreshed")
		return {'FINISHED'}

class GITBLEND_OT_stash_delete(bpy.types.Operator):
	bl_idname = "gitblend.stash_delete"
	bl_label = "Delete From Stash"
	bl_description = "Delete selected stash object(s) permanently"
	bl_options = {"REGISTER", "UNDO"}

	names: bpy.props.StringProperty(  # type: ignore
		name="Names",
		description="Comma separated stash object names to delete",
		default=""
	)

	@classmethod
	def poll(cls, context):  # type: ignore
		return True

	def execute(self, context):
		scene = bpy.data.scenes.get(STASH_SCENE_NAME)
		if scene is None:
			self.report({'WARNING'}, "No stash scene")
			return {'CANCELLED'}
		names = [n.strip() for n in self.names.split(',') if n.strip()]
		if not names:
			self.report({'WARNING'}, "No object names provided")
			return {'CANCELLED'}
		deleted = 0
		for name in names:
			obj = scene.objects.get(name)
			if not obj:
				continue
			try:
				bpy.data.objects.remove(obj, do_unlink=True)
				deleted += 1
			except Exception:
				continue
		self.report({'INFO'}, f"Deleted {deleted} object(s) from stash")
		_post_stash_mutation(context)
		return {'FINISHED'}

def _tag_redraw():
	try:
		for window in bpy.context.window_manager.windows:  # type: ignore
			for area in window.screen.areas:
				if area.type == 'VIEW_3D':
					area.tag_redraw()
	except Exception:
		pass


__all__ = [
	"GITBLEND_OT_stash_add",
	"GITBLEND_OT_stash_append",
	"GITBLEND_OT_stash_delete",
]

