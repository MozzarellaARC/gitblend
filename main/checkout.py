import bpy
from pathlib import Path

HEX_CHARS = set('0123456789abcdef')
UID_LENGTH = 8
CHECKOUT_COLLECTION_NAME = ".checkout"


def _ensure_checkout_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
	collection = bpy.data.collections.get(CHECKOUT_COLLECTION_NAME)
	if collection is None:
		collection = bpy.data.collections.new(CHECKOUT_COLLECTION_NAME)
	if CHECKOUT_COLLECTION_NAME not in {child.name for child in scene.collection.children}:
		scene.collection.children.link(collection)
	return collection


def _assign_to_checkout_collection(obj: bpy.types.Object, checkout_collection: bpy.types.Collection) -> None:
	if checkout_collection not in obj.users_collection:
		checkout_collection.objects.link(obj)
	for other in tuple(obj.users_collection):
		if other != checkout_collection:
			other.objects.unlink(obj)

def _has_uid_suffix(name: str) -> bool:
	parts = name.rsplit('_', 1)
	if len(parts) != 2:
		return False
	suffix = parts[1]
	return len(suffix) == UID_LENGTH and all(c in HEX_CHARS for c in suffix)


def _base_name_from_uid(name: str) -> str | None:
	if not _has_uid_suffix(name):
		return None
	return name.rsplit('_', 1)[0]


def _is_numbered_variant(name: str, base_name: str) -> bool:
	if not name.startswith(base_name + '.'):
		return False
	suffix = name[len(base_name) + 1:]
	return suffix.isdigit()


def _remove_existing_object_variants(base_name: str, preserve: set[bpy.types.Object] | None = None) -> int:
	removed = 0
	preserve = preserve or set()
	for obj in list(bpy.data.objects):
		if obj in preserve:
			continue
		if obj.name == base_name or _is_numbered_variant(obj.name, base_name):
			bpy.data.objects.remove(obj, do_unlink=True)
			removed += 1
	if removed:
		bpy.ops.outliner.orphans_purge(do_recursive=True)
	return removed

def cleanup_temp_objects():
	"""Remove all objects with UID suffix from the scene"""
	temp_objects = [obj for obj in bpy.context.scene.objects if _has_uid_suffix(obj.name)]
	for obj in temp_objects:
		bpy.data.objects.remove(obj, do_unlink=True)
	bpy.ops.outliner.orphans_purge(do_recursive=True)
	return len(temp_objects)

def has_temp_objects():
	"""Check if there are any objects with UID suffix in the scene"""
	return any(_has_uid_suffix(obj.name) for obj in bpy.context.scene.objects)

class GITBLEND_OT_Single_Object_Checkout(bpy.types.Operator):
	"""Finalize the currently selected preview object (remove UID suffix)"""
	bl_idname = "gitblend.single_object_checkout"
	bl_label = "Single Object Checkout"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# Get the currently selected object
		selected_obj = context.active_object
		
		if selected_obj is None:
			self.report({'WARNING'}, "No object selected")
			return {'CANCELLED'}

		# Check if the selected object has a UID suffix (8-character hex at the end)
		base_name = _base_name_from_uid(selected_obj.name)
		if base_name is None:
			self.report({'WARNING'}, f"'{selected_obj.name}' is not a preview object")
			return {'CANCELLED'}

		# Remove UID suffix to finalize the object
		selected_obj.name = base_name
		checkout_collection = _ensure_checkout_collection(context.scene)
		_assign_to_checkout_collection(selected_obj, checkout_collection)
		self.report({'INFO'}, f"Finalized: {base_name}")
		
		return {'FINISHED'}

class GITBLEND_OT_PreCheckout(bpy.types.Operator):
	bl_idname = "gitblend.pre_checkout"
	bl_label = "Pre-Checkout"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# First, cleanup any existing temp objects
		cleanup_temp_objects()
		
		scene = context.scene.gitblend_props
		gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
		index = scene.commit_history[scene.i]
		
		# Look for objects in the objects/{uid} directory instead of a single file
		objects_dir = gitblend_dir / "objects" / index.uid
		
		# Check if objects directory exists
		if not objects_dir.exists():
			self.report({'ERROR'}, f"Commit objects not found: {objects_dir}")
			return {'CANCELLED'}

		try:
			imported_count = 0
			checkout_collection = _ensure_checkout_collection(context.scene)
			# Load all .blend files from the objects directory
			for blend_file in objects_dir.glob("*.blend"):
				with bpy.data.libraries.load(str(blend_file), link=False) as (data_from, data_to):
					# Load all objects from this blend file
					object_names = list(data_from.objects)
					data_to.objects = object_names[:]
				
				# Link the loaded objects to the current scene with UID suffix,
				# preserving the original name prior to Blender's de-duplication.
				for original_name, obj in zip(object_names, data_to.objects):
					if obj is not None:
						# Add UID suffix to the object name
						obj.name = f"{original_name}_{index.uid}"
						_assign_to_checkout_collection(obj, checkout_collection)
						imported_count += 1
					
			if imported_count > 0:
				self.report({'INFO'}, f"Preview: {imported_count} object(s) loaded as temporary from commit '{index.uid}'")
			else:
				self.report({'WARNING'}, f"No objects found in commit '{index.uid}'")
				
		except Exception as e:
			self.report({'ERROR'}, f"Failed to preview commit: {str(e)}")
			return {'CANCELLED'}
				
		return {'FINISHED'}

class GITBLEND_OT_Checkout(bpy.types.Operator):
	"""Checkout a specific commit"""
	bl_idname = "gitblend.checkout"
	bl_label = "Checkout Commit"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# Check if there are objects with UID suffix to finalize
		temp_objects = [obj for obj in bpy.context.scene.objects if _has_uid_suffix(obj.name)]
		
		if not temp_objects:
			# No temp objects, do regular checkout
			scene = context.scene.gitblend_props
			gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
			index = scene.commit_history[scene.i]
			
			# Look for objects in the objects/{uid} directory
			objects_dir = gitblend_dir / "objects" / index.uid
			
			if not objects_dir.exists():
				self.report({'ERROR'}, f"Commit objects not found: {objects_dir}")
				return {'CANCELLED'}

			try:
				imported_count = 0
				removed_count = 0
				checkout_collection = _ensure_checkout_collection(context.scene)
				# Load all .blend files from the objects directory
				for blend_file in objects_dir.glob("*.blend"):
					with bpy.data.libraries.load(str(blend_file), link=False) as (data_from, data_to):
						# Load all objects from this blend file
						object_names = list(data_from.objects)
						data_to.objects = object_names[:]
					
					# Link the loaded objects to the current scene
					for original_name, obj in zip(object_names, data_to.objects):
						if obj is None:
							continue
						removed_count += _remove_existing_object_variants(original_name)
						obj.name = original_name
						_assign_to_checkout_collection(obj, checkout_collection)
						imported_count += 1
				
				message = f"Imported {imported_count} object(s)"
				if removed_count:
					message += f" (replaced {removed_count} existing)"
				self.report({'INFO'}, message)
			except Exception as e:
				self.report({'ERROR'}, f"Failed to checkout commit: {str(e)}")
				return {'CANCELLED'}
		else:
			# Finalize objects by removing UID suffix
			finalized_count = 0
			checkout_collection = _ensure_checkout_collection(context.scene)
			for obj in temp_objects:
				# Remove UID suffix
				base_name = _base_name_from_uid(obj.name)
				if base_name:
					_remove_existing_object_variants(base_name, preserve={obj})
					obj.name = base_name
					_assign_to_checkout_collection(obj, checkout_collection)
					finalized_count += 1
					
			self.report({'INFO'}, f"Finalized {finalized_count} object(s) from preview")
				
		return {'FINISHED'}