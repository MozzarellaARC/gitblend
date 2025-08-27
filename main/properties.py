import bpy


class GITBLEND_SaveEvent(bpy.types.PropertyGroup):
    """Single save event entry."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    filepath: bpy.props.StringProperty(name="Filepath")


class GITBLEND_Properties(bpy.types.PropertyGroup):
    """Root properties for GITBLEND add-on."""
    save_events: bpy.props.CollectionProperty(type=GITBLEND_SaveEvent)
    save_events_index: bpy.props.IntProperty(default=0)


def register_properties():
    bpy.utils.register_class(GITBLEND_SaveEvent)
    bpy.utils.register_class(GITBLEND_Properties)
    bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)


def unregister_properties():
    del bpy.types.Scene.gitblend_props
    bpy.utils.unregister_class(GITBLEND_Properties)
    bpy.utils.unregister_class(GITBLEND_SaveEvent)