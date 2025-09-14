import bpy # type: ignore

from .commit import GITBLEND_OT_commit
from .initialize import GITBLEND_OT_initialize

_OPERATORS = (
    GITBLEND_OT_initialize,
    GITBLEND_OT_commit,
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