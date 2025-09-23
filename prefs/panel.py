import bpy

class GITBLEND_UL_History_List(bpy.types.UIList):
	"""UIList to display commit items"""
	bl_idname = "GITBLEND_UL_history_list"

	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		commit = item
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			# Split layout for message, timestamp, and preview checkbox
			split = layout.split(factor=0.4)
			split.prop(commit, "message", text="", emboss=False, icon='FILE_TICK')
			
			split2 = split.split(factor=0.8)
			split2.label(text=commit.timestamp, icon='TIME')
			
			# Add preview checkbox on the right
			preview_col = split2.column()
			preview_col.prop(commit, "is_previewed", text="", icon='HIDE_OFF' if commit.is_previewed else 'HIDE_ON')
		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label(text="", icon='FILE_TICK')
	
def draw_gitblend_interface(layout, context):
	"""Shared function to draw the GitBlend interface"""
	scene = context.scene.gitblend_props

	box = layout.box()
	box.label(text="Commit History", icon='IPO_BEZIER')
	row = box.row()
	row.template_list(listtype_name="GITBLEND_UL_history_list",
					   list_id="commit_history",
					   dataptr=scene, 
					   propname="commit_history",
					   active_dataptr=scene,
					   active_propname="i",
					   type='DEFAULT')
					   
	
	# Add action buttons column next to the list
	col = row.column()
	col.operator("gitblend.refresh", text="", icon='FILE_REFRESH')
	col.operator("gitblend.checkout", text="", icon='IMPORT')
	col.operator("gitblend.single_object_checkout", text="", icon='OBJECT_DATA')
	col.operator("gitblend.serde", text="", icon='QUESTION')
	col.operator("gitblend.purge", text="", icon='TRASH')
	
	row = layout.row()
	row.operator("gitblend.commit",
				  text="Commit Changes" if scene.commit_history.items() else "Initialize / Sync",
				  icon='FILE_TICK')

	# Show commit size info if available
	if scene.commit_history.items():
		box = layout.box()
		box.label(text="Commit Info", icon='INFO')
		
		# Show current/selected commit info
		if len(scene.commit_history) > 0 and scene.i < len(scene.commit_history):
			current_commit = scene.commit_history[scene.i]
			
			# Try to get file size if the commit has size data
			if hasattr(current_commit, 'file_size') and current_commit.file_size > 0:
				# Show file size in bytes
				size_str = f"{current_commit.file_size} bytes"
				
				row = box.row()
				row.label(text=f"Size: {size_str}", icon='FILE')
			else:
				row = box.row()
				row.label(text="Size: Unknown", icon='FILE')
			
			# Show commit hash if available
			if hasattr(current_commit, 'hash_value') and current_commit.hash_value:
				row = box.row()
				# Show only first 8 characters of hash
				short_hash = current_commit.hash_value[:8] if len(current_commit.hash_value) >= 8 else current_commit.hash_value
				row.label(text=f"Hash: {short_hash}", icon='KEYFRAME')
			
			# Show total commits count
			row = box.row()
			row.label(text=f"Commits: {len(scene.commit_history)}", icon='SEQUENCE')
	

class GITBLEND_PT_Panel(bpy.types.Panel):
	bl_label = "Git Blend"
	bl_idname = "GITBLEND_PT_panel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = '.gitblend'

	def draw(self, context):
		draw_gitblend_interface(self.layout, context)

class GITBLEND_OT_PopupWindow(bpy.types.Operator):
	"""Open Git Blend in a popup window"""
	bl_idname = "gitblend.popup_window"
	bl_label = "Git Blend"
	bl_options = {'REGISTER', 'UNDO'}
	
	def draw(self, context):
		draw_gitblend_interface(self.layout, context)

	def execute(self, context):
		return {'FINISHED'}

	def invoke(self, context, event):
		# Position the popup below the menu item using mouse coordinates
		# Use invoke_popup to create a popup that appears at a specific location
		return context.window_manager.invoke_popup(self, width=300)
		
def draw_gitblend_menu(self, context):
	layout = self.layout
	layout.operator("gitblend.popup_window", text=".gitblend")