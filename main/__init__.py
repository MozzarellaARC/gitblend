import bpy # type: ignore

from .commit import GITBLEND_OT_commit

def register_operators():
    bpy.utils.register_class(GITBLEND_OT_commit)
def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_commit)

__all__ = (
    "register_operators",
    "unregister_operators",
)