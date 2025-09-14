import bpy # type: ignore

from .commit import GITBLEND_OT_commit, GITBLEND_OT_commit_copy_scene

def register_operators():
    bpy.utils.register_class(GITBLEND_OT_commit)
    bpy.utils.register_class(GITBLEND_OT_commit_copy_scene)
def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_commit_copy_scene)
    bpy.utils.unregister_class(GITBLEND_OT_commit)

__all__ = (
    "register_operators",
    "unregister_operators",
)