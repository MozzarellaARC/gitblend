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

def unregister_properties():
	bpy.utils.unregister_class(GITBLEND_Panel)
	bpy.utils.unregister_class(GITBLEND_Properties)