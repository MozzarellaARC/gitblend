import bpy # type: ignore # type: ignore

# from .properties import (
# 	GITBLEND_Properties,
# )

from .panel import (
	GITBLEND_PT_Panel,
	GITBLEND_UL_commit_history,
)


def register_prefs():
	# bpy.utils.register_class(GITBLEND_Properties)
	bpy.utils.register_class(GITBLEND_UL_commit_history)
	bpy.utils.register_class(GITBLEND_PT_Panel)

def unregister_prefs():
	bpy.utils.unregister_class(GITBLEND_PT_Panel)
	bpy.utils.unregister_class(GITBLEND_UL_commit_history)
	# bpy.utils.unregister_class(GITBLEND_Properties)

__all__ = (
	"register_prefs",
	"unregister_prefs",
)