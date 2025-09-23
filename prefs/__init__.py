import re
import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
	GITBLEND_CommitItem,
)

from .panel import (
	GITBLEND_OT_PopupWindow,
	GITBLEND_PT_Panel,
	GITBLEND_UL_History_List,
	draw_gitblend_menu
)

cls = [
	GITBLEND_CommitItem,
	GITBLEND_Properties,
	GITBLEND_OT_PopupWindow,
	GITBLEND_PT_Panel,
	GITBLEND_UL_History_List,
]

def register_prefs():
	for c in cls:
		try:
			bpy.utils.register_class(c)
		except ValueError:
			# Class is already registered, skip silently
			pass
		except Exception as e:
			print(f"Error registering class {c.__name__}: {e}")
	
	try:
		if not hasattr(bpy.types.Scene, 'gitblend_props'):
			bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)
	except Exception as e:
		print(f"Error adding PointerProperty to Scene: {e}")
	
	try:
		# Check if menu is already added to avoid duplicates
		if draw_gitblend_menu not in bpy.types.VIEW3D_MT_editor_menus._dyn_ui_initialize():
			bpy.types.VIEW3D_MT_editor_menus.append(draw_gitblend_menu)
	except AttributeError:
		# _dyn_ui_initialize might not exist, fallback to simple check
		try:
			bpy.types.VIEW3D_MT_editor_menus.append(draw_gitblend_menu)
		except Exception as e:
			print(f"Error adding menu: {e}")
	except Exception as e:
		print(f"Error adding menu: {e}")

def unregister_prefs():
	for c in reversed(cls):
		try:
			bpy.utils.unregister_class(c)
		except RuntimeError:
			# Class is not registered, skip silently
			pass
		except Exception as e:
			print(f"Error unregistering class {c.__name__}: {e}")
	
	try:
		bpy.types.VIEW3D_MT_editor_menus.remove(draw_gitblend_menu)
	except ValueError:
		# Menu not in list, skip silently
		pass
	except Exception as e:
		print(f"Error removing menu: {e}")
	
	try:
		if hasattr(bpy.types.Scene, 'gitblend_props'):
			del bpy.types.Scene.gitblend_props
	except Exception as e:
		print(f"Error removing PointerProperty from Scene: {e}")

__all__ = (
	"register_prefs",
	"unregister_prefs",
)