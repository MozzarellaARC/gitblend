import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
)

from .panel import (
	GITBLEND_Panel,
)



def register_prefs():
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)  # type: ignore
	bpy.utils.register_class(GITBLEND_Panel)

def unregister_prefs():
	bpy.utils.unregister_class(GITBLEND_Panel)
	del bpy.types.Scene.gitblend_props
	bpy.utils.unregister_class(GITBLEND_Properties)

__all__ = (
	"register_prefs",
	"unregister_prefs",
)