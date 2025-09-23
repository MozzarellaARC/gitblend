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
		except:
			raise RuntimeError(f"Failed to register class: {c.__name__}")
	try:
		bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)
		bpy.types.VIEW3D_MT_editor_menus.append(draw_gitblend_menu)
	except:
		raise RuntimeError("Failed to add PointerProperty to Scene")

def unregister_prefs():
	for c in reversed(cls):
		try:
			bpy.utils.unregister_class(c)
		except:
			raise RuntimeError(f"Failed to unregister class: {c.__name__}")
	try:
		bpy.types.VIEW3D_MT_editor_menus.remove(draw_gitblend_menu)
		del bpy.types.Scene.gitblend_props
	except:
		raise RuntimeError("Failed to remove PointerProperty from Scene")

__all__ = (
	"register_prefs",
	"unregister_prefs",
)