import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
)

from .panel import (
	GITBLEND_Panel,
	GITBLEND_OT_refresh,
)

__all__ = (
	"register_properties",
	"unregister_properties",
)

def register_properties():
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.utils.register_class(GITBLEND_Panel)
	bpy.utils.register_class(GITBLEND_OT_refresh)
	# Scene-level commit message so the panel can bind reliably
	bpy.types.Scene.gitblend_commit_message = bpy.props.StringProperty(  # type: ignore
		name="Message",
		description="Commit message",
		default="",
	)

def unregister_properties():
	bpy.utils.unregister_class(GITBLEND_OT_refresh)
	bpy.utils.unregister_class(GITBLEND_Panel)
	bpy.utils.unregister_class(GITBLEND_Properties)
	# Remove Scene property if present
	if hasattr(bpy.types.Scene, 'gitblend_commit_message'):
		del bpy.types.Scene.gitblend_commit_message