import bpy # type: ignore # type: ignore

from .properties import (
	register_properties,
	unregister_properties,
)

from .panel import (
	GITBLEND_PT_Panel,
	GITBLEND_UL_commit_history,
)


def register_prefs():
	register_properties()
	bpy.utils.register_class(GITBLEND_UL_commit_history)
	bpy.utils.register_class(GITBLEND_PT_Panel)

def unregister_prefs():
	bpy.utils.unregister_class(GITBLEND_PT_Panel)
	bpy.utils.unregister_class(GITBLEND_UL_commit_history)
	unregister_properties()

__all__ = (
	"register_prefs",
	"unregister_prefs",
)