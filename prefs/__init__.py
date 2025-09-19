import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
	GITBLEND_CommitEntry,
)

from .panel import (
	GITBLEND_Panel,
	GITBLEND_UL_commit_history,
)

def register_prefs():
	bpy.utils.register_class(GITBLEND_CommitEntry)
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.utils.register_class(GITBLEND_UL_commit_history)
	bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)  # type: ignore
	bpy.utils.register_class(GITBLEND_Panel)

def unregister_prefs():
	bpy.utils.unregister_class(GITBLEND_Panel)
	bpy.utils.unregister_class(GITBLEND_UL_commit_history)
	del bpy.types.Scene.gitblend_props
	bpy.utils.unregister_class(GITBLEND_Properties)
	bpy.utils.unregister_class(GITBLEND_CommitEntry)

__all__ = (
	"register_prefs",
	"unregister_prefs",
)