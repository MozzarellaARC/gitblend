import bpy
from ..prefs.properties import (
    GITBLEND_StringItem,
    GITBLEND_ChangeLogEntry,
    GITBLEND_Properties,
)

__all__ = (
    "register_properties",
    "unregister_properties",
)

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