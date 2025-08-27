import bpy


class GITBLEND_SaveEvent(bpy.types.PropertyGroup):
    """Single save event entry."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    filepath: bpy.props.StringProperty(name="Filepath")

class GITBLEND_ChangeLogEntry(bpy.types.PropertyGroup):
    """Single commit/change-log entry."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    message: bpy.props.StringProperty(name="Message")

class GITBLEND_StringItem(bpy.types.PropertyGroup):
    """Simple string item for dynamic lists."""
    # Use 'name' so default UI list shows it; editable in panel
    name: bpy.props.StringProperty(name="Value", default="")

def _string_enum_items(self, context):
    """Items callback for the dropdown showing current string_items.
    Returns list of (identifier, name, description) tuples.
    Identifier uses the index to guarantee uniqueness.
    """
    items = []
    try:
        for i, it in enumerate(self.string_items):
            name = it.name or f"Item {i+1}"
            items.append((str(i), name, name))
    except Exception:
        pass
    if not items:
        # Provide a dummy option when empty so the UI still draws a dropdown
        items = [("-1", "<no items>", "No items available")]
    return items

def _on_selected_string_update(self, context):
    """Keep the index in sync with the dropdown selection."""
    try:
        sel = getattr(self, "selected_string", "")
        idx = int(sel) if sel not in {"", None, "-1"} else -1
    except Exception:
        idx = -1
    if 0 <= idx < len(self.string_items):
        self.string_items_index = idx


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
    gitblend_branch: bpy.props.StringProperty(
        name="Gitblend Branch Name",
        description="Preferred top-level collection name to use during initialization",
        default="main",
    )
    # Dynamic list of strings
    string_items: bpy.props.CollectionProperty(type=GITBLEND_StringItem)
    string_items_index: bpy.props.IntProperty(default=0)
    selected_string: bpy.props.EnumProperty(
        name="Select",
        description="Choose one of the string items",
    items=_string_enum_items,
    update=_on_selected_string_update,
    )


def register_properties():
    bpy.utils.register_class(GITBLEND_StringItem)
    bpy.utils.register_class(GITBLEND_SaveEvent)
    bpy.utils.register_class(GITBLEND_ChangeLogEntry)
    bpy.utils.register_class(GITBLEND_Properties)
    bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)


def unregister_properties():
    if hasattr(bpy.types.Scene, "gitblend_props"):
        del bpy.types.Scene.gitblend_props
    # Unregister in reverse order of registration to honor dependencies
    for cls in (GITBLEND_Properties, GITBLEND_ChangeLogEntry, GITBLEND_SaveEvent, GITBLEND_StringItem):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass