import bpy

from .commit import (GITBLEND_OT_commit,
                     GITBLEND_OT_initialize)

from .operators import (GITBLEND_OT_branch_add,
                        GITBLEND_OT_branch_remove,
                        GITBLEND_OT_undo_commit,
                        GITBLEND_OT_discard_changes,)
from .checkout import GITBLEND_OT_checkout

def register_operators():
    bpy.utils.register_class(GITBLEND_OT_commit)
    bpy.utils.register_class(GITBLEND_OT_initialize)
    bpy.utils.register_class(GITBLEND_OT_branch_add)
    bpy.utils.register_class(GITBLEND_OT_branch_remove)
    bpy.utils.register_class(GITBLEND_OT_undo_commit)
    bpy.utils.register_class(GITBLEND_OT_discard_changes)
    bpy.utils.register_class(GITBLEND_OT_checkout)


def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_discard_changes)
    bpy.utils.unregister_class(GITBLEND_OT_undo_commit)
    bpy.utils.unregister_class(GITBLEND_OT_branch_remove)
    bpy.utils.unregister_class(GITBLEND_OT_branch_add)
    bpy.utils.unregister_class(GITBLEND_OT_initialize)
    bpy.utils.unregister_class(GITBLEND_OT_commit)
    try:
        bpy.utils.unregister_class(GITBLEND_OT_checkout)
    except RuntimeError:
        pass

__all__ = [
    "register_operators",
    "unregister_operators",
    ]