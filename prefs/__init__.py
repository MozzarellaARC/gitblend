import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
)

from .panel import (
	GITBLEND_Panel,
)

__all__ = (
	"register_properties",
	"unregister_properties",
)

def register_properties():
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.utils.register_class(GITBLEND_Panel)
	# Scene-level commit message so the panel can bind reliably
	try:
		import bpy as _bpy  # type: ignore
		_bpy.types.Scene.gitblend_commit_message = _bpy.props.StringProperty(  # type: ignore
			name="Message",
			description="Commit message",
			default="",
		)
	except Exception:
		pass

def unregister_properties():
	bpy.utils.unregister_class(GITBLEND_Panel)
	bpy.utils.unregister_class(GITBLEND_Properties)
	# Remove Scene property if present
	try:
		import bpy as _bpy  # type: ignore
		if hasattr(_bpy.types.Scene, 'gitblend_commit_message'):
			del _bpy.types.Scene.gitblend_commit_message
	except Exception:
		pass