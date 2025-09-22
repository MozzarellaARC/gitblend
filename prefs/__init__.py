import re
import bpy # type: ignore # type: ignore

from .properties import (
	GITBLEND_Properties,
	GITBLEND_CommitItem,
)

from .panel import (
	register_panel,
	unregister_panel,
)


def register_prefs():
	bpy.utils.register_class(GITBLEND_CommitItem)
	bpy.utils.register_class(GITBLEND_Properties)
	bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)
	register_panel()

def unregister_prefs():
	unregister_panel()
	del bpy.types.Scene.gitblend_props
	bpy.utils.unregister_class(GITBLEND_Properties)
	bpy.utils.unregister_class(GITBLEND_CommitItem)

__all__ = (
	"register_prefs",
	"unregister_prefs",
)