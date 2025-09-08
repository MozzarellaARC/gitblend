import bpy

from .operators import (
    GITBLEND_OT_commit,
    GITBLEND_OT_initialize,
    GITBLEND_OT_string_add,
    GITBLEND_OT_string_remove,
    GITBLEND_OT_undo_commit,
    GITBLEND_OT_discard_changes,
    GITBLEND_OT_checkout_log,
)
from .panel import (
    GITBLEND_UL_ChangeLog,
    GITBLEND_Panel,
)

__all__ = (
    "register_main",
    "unregister_main",
)

def register_main():
    bpy.utils.register_class(GITBLEND_OT_commit)
    bpy.utils.register_class(GITBLEND_OT_initialize)
    bpy.utils.register_class(GITBLEND_OT_string_add)
    bpy.utils.register_class(GITBLEND_OT_string_remove)
    bpy.utils.register_class(GITBLEND_OT_undo_commit)
    bpy.utils.register_class(GITBLEND_OT_discard_changes)
    bpy.utils.register_class(GITBLEND_OT_checkout_log)
    
    bpy.utils.register_class(GITBLEND_UL_ChangeLog)
    bpy.utils.register_class(GITBLEND_Panel)


def unregister_main():
    bpy.utils.unregister_class(GITBLEND_OT_discard_changes)
    bpy.utils.unregister_class(GITBLEND_OT_undo_commit)
    bpy.utils.unregister_class(GITBLEND_OT_string_remove)
    bpy.utils.unregister_class(GITBLEND_OT_string_add)
    bpy.utils.unregister_class(GITBLEND_OT_initialize)
    bpy.utils.unregister_class(GITBLEND_OT_commit)
    try:
        bpy.utils.unregister_class(GITBLEND_OT_checkout_log)
    except RuntimeError:
        pass
    bpy.utils.unregister_class(GITBLEND_Panel)
    bpy.utils.unregister_class(GITBLEND_UL_ChangeLog)