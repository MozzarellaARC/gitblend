import bpy
from pathlib import Path

def cleanup_temp_objects():
	"""Remove all objects with _temp suffix from the scene"""
	temp_objects = [obj for obj in bpy.context.scene.objects if obj.name.endswith('_temp')]
	for obj in temp_objects:
		bpy.data.objects.remove(obj, do_unlink=True)
	bpy.ops.outliner.orphans_purge(do_recursive=True)
	return len(temp_objects)

def has_temp_objects():
	"""Check if there are any temp objects in the scene"""
	return any(obj.name.endswith('_temp') for obj in bpy.context.scene.objects)

class GITBLEND_OT_ClearPreview(bpy.types.Operator):
	"""Clear all preview objects"""
	bl_idname = "gitblend.clear_preview"
	bl_label = "Clear Preview"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		count = cleanup_temp_objects()
		if count > 0:
			self.report({'INFO'}, f"Cleared {count} preview object(s)")
		else:
			self.report({'INFO'}, "No preview objects to clear")
		return {'FINISHED'}

class GITBLEND_OT_PreCheckout(bpy.types.Operator):
	bl_idname = "gitblend.pre_checkout"
	bl_label = "Pre-Checkout"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# First, cleanup any existing temp objects
		cleanup_count = cleanup_temp_objects()
		
		scene = context.scene.gitblend_props
		gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
		index = scene.commit_history[scene.i]
		filepath = gitblend_dir / index.filename

		# Check if file exists
		if not filepath.exists():
			self.report({'ERROR'}, f"Commit file not found: {filepath}")
			return {'CANCELLED'}

		try:
			with bpy.data.libraries.load(str(filepath), link=False) as (data_from, data_to):
				# Load based on message
				data_to.objects = [name for name in data_from.objects if name == index.message]
				
			# Link the loaded objects to the current scene with _temp suffix
			imported_count = 0
			for obj in data_to.objects:
				if obj is not None:
					# Add _temp suffix to the object name
					obj.name = f"{obj.name}_temp"
					context.collection.objects.link(obj)
					imported_count += 1
					
			if imported_count > 0:
				self.report({'INFO'}, f"Preview: {imported_count} object(s) loaded as temporary from '{index.message}'")
			else:
				self.report({'WARNING'}, f"No objects found matching '{index.message}' in commit")
				
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
		# Check if there are temp objects to finalize
		temp_objects = [obj for obj in bpy.context.scene.objects if obj.name.endswith('_temp')]
		
		if not temp_objects:
			# No temp objects, do regular checkout
			scene = context.scene.gitblend_props
			gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
			index = scene.commit_history[scene.i]
			filepath = gitblend_dir / index.filename

			with bpy.data.libraries.load(str(filepath), link=False) as (data_from, data_to):
				# Load based on message
				data_to.objects = [name for name in data_from.objects if name == index.message]
				
			# Link the loaded objects to the current scene
			imported_count = 0
			for obj in data_to.objects:
				if obj is not None:
					context.collection.objects.link(obj)
					imported_count += 1
					
			self.report({'INFO'}, f"Imported {imported_count} object(s)")
		else:
			# Finalize temp objects by removing _temp suffix
			finalized_count = 0
			for obj in temp_objects:
				# Remove _temp suffix
				if obj.name.endswith('_temp'):
					obj.name = obj.name[:-5]  # Remove '_temp' (5 characters)
					finalized_count += 1
					
			self.report({'INFO'}, f"Finalized {finalized_count} object(s) from preview")
				
		return {'FINISHED'}