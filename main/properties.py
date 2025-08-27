import bpy


class GITBLEND_SaveEvent(bpy.types.PropertyGroup):
    """Single save event entry."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    filepath: bpy.props.StringProperty(name="Filepath")

class GITBLEND_ChangeLogEntry(bpy.types.PropertyGroup):
    """Single commit/change-log entry."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    message: bpy.props.StringProperty(name="Message")


class GITBLEND_Properties(bpy.types.PropertyGroup):
    """Root properties for GITBLEND add-on."""
    save_events: bpy.props.CollectionProperty(type=GITBLEND_SaveEvent)
    save_events_index: bpy.props.IntProperty(default=0)
    # Change log
    changes_log: bpy.props.CollectionProperty(type=GITBLEND_ChangeLogEntry)
    changes_log_index: bpy.props.IntProperty(default=0)
    commit_message: bpy.props.StringProperty(
        name="Commit Message",
        description="Describe the changes to record in the log",
    default=""
    )


def register_properties():
    bpy.utils.register_class(GITBLEND_SaveEvent)
    bpy.utils.register_class(GITBLEND_ChangeLogEntry)
    bpy.utils.register_class(GITBLEND_Properties)
    bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)


def unregister_properties():
    del bpy.types.Scene.gitblend_props
    bpy.utils.unregister_class(GITBLEND_Properties)
    bpy.utils.unregister_class(GITBLEND_ChangeLogEntry)
    bpy.utils.unregister_class(GITBLEND_SaveEvent)