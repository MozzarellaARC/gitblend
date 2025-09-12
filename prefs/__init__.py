import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
)

from .panel import (
	GITBLEND_Panel,
)

def register_prefs():
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.utils.register_class(GITBLEND_Panel)

def unregister_prefs():
	bpy.utils.unregister_class(GITBLEND_Panel)
	bpy.utils.unregister_class(GITBLEND_Properties)

__all__ = (
	"register_prefs",
	"unregister_prefs",
)