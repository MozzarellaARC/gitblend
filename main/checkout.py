import bpy
from pathlib import Path

class GITBLEND_OT_Checkout(bpy.types.Operator):
	"""Checkout a specific commit"""
	bl_idname = "gitblend.checkout"
	bl_label = "Checkout Commit"
	bl_options = {'REGISTER', 'UNDO'}


	def execute(self, context):

		scene = context.scene.gitblend_props
		gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
		index = scene.commit_history[scene.i]
		filepath = gitblend_dir / index.filename

		with bpy.data.libraries.load(str(filepath), link=False) as (data_from, data_to):
			# Load based on message
			data_to.objects = [name for name in data_from.objects if name == index.message]
			
		# Link the loaded objects to the current scene
		for obj in data_to.objects:
			if obj is not None:
				context.collection.objects.link(obj)
				
		return {'FINISHED'}