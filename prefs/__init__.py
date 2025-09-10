import bpy

from .panel import GITBLEND_Panel, GITBLEND_UL_ChangeLog
from .properties import GITBLEND_Properties ,GITBLEND_StringItem, GITBLEND_ChangeLogEntry


def register_properties():
    bpy.utils.register_class(GITBLEND_StringItem)
    bpy.utils.register_class(GITBLEND_ChangeLogEntry)
    bpy.utils.register_class(GITBLEND_Properties)
    bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)


def unregister_properties():
    if hasattr(bpy.types.Scene, "gitblend_props"):
        del bpy.types.Scene.gitblend_props
    # Unregister in reverse order of registration to honor dependencies
    for cls in (GITBLEND_Properties, GITBLEND_ChangeLogEntry, GITBLEND_StringItem):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

def register_panel():
    bpy.utils.register_class(GITBLEND_UL_ChangeLog)
    bpy.utils.register_class(GITBLEND_Panel)

def unregister_panel():
    try:
        bpy.utils.unregister_class(GITBLEND_Panel)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(GITBLEND_UL_ChangeLog)
    except RuntimeError:
        pass

__all__ = [
    "register_properties",
    "unregister_properties",
    "register_panel",
    "unregister_panel",
]