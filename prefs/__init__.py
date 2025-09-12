import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
)

from .panel import (
	GITBLEND_Panel,
)

from .preferences import (
	GITBLEND_OT_InstallJsondiff,
	GITBLEND_OT_UninstallJsondiff,
	GITBLEND_OT_CheckJsondiff,
)

def register_prefs():
	bpy.utils.register_class(GITBLEND_OT_InstallJsondiff)
	bpy.utils.register_class(GITBLEND_OT_UninstallJsondiff)
	bpy.utils.register_class(GITBLEND_OT_CheckJsondiff)
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)  # type: ignore
	bpy.utils.register_class(GITBLEND_Panel)

def unregister_prefs():
	bpy.utils.unregister_class(GITBLEND_Panel)
	del bpy.types.Scene.gitblend_props
	bpy.utils.unregister_class(GITBLEND_Properties)
	bpy.utils.unregister_class(GITBLEND_OT_CheckJsondiff)
	bpy.utils.unregister_class(GITBLEND_OT_UninstallJsondiff)
	bpy.utils.unregister_class(GITBLEND_OT_InstallJsondiff)

__all__ = (
	"register_prefs",
	"unregister_prefs",
)