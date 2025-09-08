import bpy # type: ignore

from .operators import (
    GITBLEND_OT_commit,
)

__all__ = (
    "register_main",
    "unregister_main",
)

def register_main():
    bpy.utils.register_class(GITBLEND_OT_commit)

def unregister_main():
    bpy.utils.unregister_class(GITBLEND_OT_commit)