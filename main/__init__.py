import bpy # type: ignore

from .checkout import (
	GITBLEND_OT_Checkout
)

from .commit import (
	GITBLEND_OT_Commit
)

from .refresh import (
	GITBLEND_OT_Refresh,
	GITBLEND_OT_Serde
)


def register_operators():
	bpy.utils.register_class(GITBLEND_OT_Checkout)
	bpy.utils.register_class(GITBLEND_OT_Commit)
	bpy.utils.register_class(GITBLEND_OT_Refresh)
	bpy.utils.register_class(GITBLEND_OT_Serde)

def unregister_operators():
	bpy.utils.unregister_class(GITBLEND_OT_Checkout)
	bpy.utils.unregister_class(GITBLEND_OT_Refresh)
	bpy.utils.unregister_class(GITBLEND_OT_Commit)
	bpy.utils.unregister_class(GITBLEND_OT_Serde)


__all__ = (
	"register_operators",
	"unregister_operators",
)