import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
	GITBLEND_CommitItem,
)

from .panel import (
	GITBLEND_Panel,
	GITBLEND_UL_CommitHistory,
)

def register_prefs():
	bpy.utils.register_class(GITBLEND_CommitItem)
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)  # type: ignore
	bpy.utils.register_class(GITBLEND_UL_CommitHistory)
	bpy.utils.register_class(GITBLEND_Panel)

def unregister_prefs():
	bpy.utils.unregister_class(GITBLEND_Panel)
	bpy.utils.unregister_class(GITBLEND_UL_CommitHistory)
	del bpy.types.Scene.gitblend_props
	bpy.utils.unregister_class(GITBLEND_Properties)
	bpy.utils.unregister_class(GITBLEND_CommitItem)

__all__ = (
	"register_prefs",
	"unregister_prefs",
)