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
		
		# Also clear all preview checkboxes
		scene = context.scene.gitblend_props
		cleared_checkboxes = 0
		for commit in scene.commit_history:
			if commit.is_previewed:
				commit.is_previewed = False
				cleared_checkboxes += 1
		
		if count > 0 or cleared_checkboxes > 0:
			self.report({'INFO'}, f"Cleared {count} preview object(s) and {cleared_checkboxes} checkbox(es)")
		else:
			self.report({'INFO'}, "No preview objects or checkboxes to clear")
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
		
		# Look for objects in the objects/{uid} directory instead of a single file
		objects_dir = gitblend_dir / "objects" / index.uid
		
		# Check if objects directory exists
		if not objects_dir.exists():
			self.report({'ERROR'}, f"Commit objects not found: {objects_dir}")
			return {'CANCELLED'}

		try:
			imported_count = 0
			# Load all .blend files from the objects directory
			for blend_file in objects_dir.glob("*.blend"):
				with bpy.data.libraries.load(str(blend_file), link=False) as (data_from, data_to):
					# Load all objects from this blend file
					data_to.objects = data_from.objects[:]
				
				# Link the loaded objects to the current scene with _temp suffix
				for obj in data_to.objects:
					if obj is not None:
						# Add _temp suffix to the object name
						obj.name = f"{obj.name}_temp"
						context.collection.objects.link(obj)
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
		# Check if there are temp objects to finalize
		temp_objects = [obj for obj in bpy.context.scene.objects if obj.name.endswith('_temp')]
		
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
				# Load all .blend files from the objects directory
				for blend_file in objects_dir.glob("*.blend"):
					with bpy.data.libraries.load(str(blend_file), link=False) as (data_from, data_to):
						# Load all objects from this blend file
						data_to.objects = data_from.objects[:]
					
					# Link the loaded objects to the current scene
					for obj in data_to.objects:
						if obj is not None:
							context.collection.objects.link(obj)
							imported_count += 1
							
				self.report({'INFO'}, f"Imported {imported_count} object(s)")
			except Exception as e:
				self.report({'ERROR'}, f"Failed to checkout commit: {str(e)}")
				return {'CANCELLED'}
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