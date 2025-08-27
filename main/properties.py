import bpy


class YANT_SaveEvent(bpy.types.PropertyGroup):
    """Single save event entry."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    filepath: bpy.props.StringProperty(name="Filepath")


class YANT_Properties(bpy.types.PropertyGroup):
    """Root properties for YANT add-on."""
    save_events: bpy.props.CollectionProperty(type=YANT_SaveEvent)
    save_events_index: bpy.props.IntProperty(default=0)


def register_properties():
    bpy.utils.register_class(YANT_SaveEvent)
    bpy.utils.register_class(YANT_Properties)
    bpy.types.Scene.yant_props = bpy.props.PointerProperty(type=YANT_Properties)


def unregister_properties():
    del bpy.types.Scene.yant_props
    bpy.utils.unregister_class(YANT_Properties)
    bpy.utils.unregister_class(YANT_SaveEvent)