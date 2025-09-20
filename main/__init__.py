import bpy # type: ignore

from .initialize import GITBLEND_OT_Initialize
from .commit import GITBLEND_OT_Commit
from .checkout import GITBLEND_OT_Checkout, GITBLEND_OT_ListCommits
from .refresh import GITBLEND_OT_RefreshCommits, GITBLEND_OT_CheckoutSelected


def register_operators():
	# Register operators
	bpy.utils.register_class(GITBLEND_OT_Initialize)
	bpy.utils.register_class(GITBLEND_OT_Commit)
	bpy.utils.register_class(GITBLEND_OT_Checkout)
	bpy.utils.register_class(GITBLEND_OT_ListCommits)
	bpy.utils.register_class(GITBLEND_OT_RefreshCommits)
	bpy.utils.register_class(GITBLEND_OT_CheckoutSelected)

def unregister_operators():
	# Unregister operators
	bpy.utils.unregister_class(GITBLEND_OT_CheckoutSelected)
	bpy.utils.unregister_class(GITBLEND_OT_RefreshCommits)
	bpy.utils.unregister_class(GITBLEND_OT_ListCommits)
	bpy.utils.unregister_class(GITBLEND_OT_Checkout)
	bpy.utils.unregister_class(GITBLEND_OT_Commit)
	bpy.utils.unregister_class(GITBLEND_OT_Initialize)


__all__ = (
	"register_operators",
	"unregister_operators",
)