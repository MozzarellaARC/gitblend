import bpy # type: ignore

from .commit import (
	GITBLEND_OT_Commit
)


def register_operators():
	bpy.utils.register_class(GITBLEND_OT_Commit)

def unregister_operators():
	bpy.utils.unregister_class(GITBLEND_OT_Commit)


__all__ = (
	"register_operators",
	"unregister_operators",
)