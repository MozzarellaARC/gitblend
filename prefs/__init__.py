import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
	GITBLEND_CommitItem,
)

from .panel import (
	GITBLEND_PT_Panel,
	GITBLEND_UL_History_List,
	GITBLEND_OT_PopupWindow,
	draw_gitblend_menu
)


def register_prefs():
	bpy.utils.register_class(GITBLEND_CommitItem)
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)
	bpy.utils.register_class(GITBLEND_UL_History_List)
	bpy.utils.register_class(GITBLEND_PT_Panel)
	bpy.utils.register_class(GITBLEND_OT_PopupWindow)
	bpy.types.VIEW3D_MT_editor_menus.append(draw_gitblend_menu)

def unregister_prefs():
	bpy.types.VIEW3D_MT_editor_menus.remove(draw_gitblend_menu)
	bpy.utils.unregister_class(GITBLEND_OT_PopupWindow)
	bpy.utils.unregister_class(GITBLEND_PT_Panel)
	bpy.utils.unregister_class(GITBLEND_UL_History_List)
	del bpy.types.Scene.gitblend_props
	bpy.utils.unregister_class(GITBLEND_Properties)
	bpy.utils.unregister_class(GITBLEND_CommitItem)

__all__ = (
	"register_prefs",
	"unregister_prefs",
)