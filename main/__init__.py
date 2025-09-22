import bpy # type: ignore

from .checkout import (
	GITBLEND_OT_Checkout,
	GITBLEND_OT_PreCheckout
)

from .commit import (
	GITBLEND_OT_Commit
)

from .refresh import (
	GITBLEND_OT_Refresh,
)


def register_operators():
	bpy.utils.register_class(GITBLEND_OT_PreCheckout)
	bpy.utils.register_class(GITBLEND_OT_Checkout)
	bpy.utils.register_class(GITBLEND_OT_Commit)
	bpy.utils.register_class(GITBLEND_OT_Refresh)

def unregister_operators():
	bpy.utils.unregister_class(GITBLEND_OT_PreCheckout)
	bpy.utils.unregister_class(GITBLEND_OT_Checkout)
	bpy.utils.unregister_class(GITBLEND_OT_Commit)
	bpy.utils.unregister_class(GITBLEND_OT_Refresh)


__all__ = (
	"register_operators",
	"unregister_operators",
)