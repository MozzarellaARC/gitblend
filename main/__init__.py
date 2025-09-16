import bpy # type: ignore

from .commit import GITBLEND_OT_commit
from .checkout import GITBLEND_OT_checkout
from .initialize import GITBLEND_OT_initialize, GITBLEND_OT_sync
from .stash import GITBLEND_OT_stash, GITBLEND_OT_unstash, GITBLEND_OT_delete_stash

_OPERATORS = (
    GITBLEND_OT_initialize,
    GITBLEND_OT_sync,
    GITBLEND_OT_commit,
    GITBLEND_OT_checkout,
    GITBLEND_OT_stash,
    GITBLEND_OT_unstash,
    GITBLEND_OT_delete_stash,
)

def register_operators():
    for op in _OPERATORS:
        bpy.utils.register_class(op)

def unregister_operators():
    for op in reversed(_OPERATORS):
        bpy.utils.unregister_class(op)

__all__ = (
    "register_operators",
    "unregister_operators",
)