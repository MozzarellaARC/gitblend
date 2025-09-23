import bpy
from pathlib import Path

def cleanup_temp_objects():
	"""Remove all objects with UID suffix from the scene"""
	temp_objects = [obj for obj in bpy.context.scene.objects if '_' in obj.name and len(obj.name.split('_')[-1]) == 8 and all(c in '0123456789abcdef' for c in obj.name.split('_')[-1])]
	for obj in temp_objects:
		bpy.data.objects.remove(obj, do_unlink=True)
	bpy.ops.outliner.orphans_purge(do_recursive=True)
	return len(temp_objects)

def has_temp_objects():
	"""Check if there are any objects with UID suffix in the scene"""
	return any('_' in obj.name and len(obj.name.split('_')[-1]) == 8 and all(c in '0123456789abcdef' for c in obj.name.split('_')[-1]) for obj in bpy.context.scene.objects)

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
		name_parts = selected_obj.name.split('_')
		if len(name_parts) < 2 or len(name_parts[-1]) != 8 or not all(c in '0123456789abcdef' for c in name_parts[-1]):
			self.report({'WARNING'}, f"'{selected_obj.name}' is not a preview object")
			return {'CANCELLED'}

		# Remove UID suffix to finalize the object
		original_name = '_'.join(name_parts[:-1])  # Remove the last part (UID)
		selected_obj.name = original_name
		self.report({'INFO'}, f"Finalized: {original_name}")
		
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
				
				# Link the loaded objects to the current scene with UID suffix
				for obj in data_to.objects:
					if obj is not None:
						# Add UID suffix to the object name
						obj.name = f"{obj.name}_{index.uid}"
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
		# Check if there are objects with UID suffix to finalize
		temp_objects = [obj for obj in bpy.context.scene.objects if '_' in obj.name and len(obj.name.split('_')[-1]) == 8 and all(c in '0123456789abcdef' for c in obj.name.split('_')[-1])]
		
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
			# Finalize objects by removing UID suffix
			finalized_count = 0
			for obj in temp_objects:
				# Remove UID suffix
				name_parts = obj.name.split('_')
				if len(name_parts) >= 2 and len(name_parts[-1]) == 8 and all(c in '0123456789abcdef' for c in name_parts[-1]):
					obj.name = '_'.join(name_parts[:-1])  # Remove the last part (UID)
					finalized_count += 1
					
			self.report({'INFO'}, f"Finalized {finalized_count} object(s) from preview")
				
		return {'FINISHED'}