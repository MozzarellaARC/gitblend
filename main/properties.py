import bpy
from .utils import refresh_change_log


class GITBLEND_ChangeLogEntry(bpy.types.PropertyGroup):
    """Single commit/change-log entry."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    message: bpy.props.StringProperty(name="Message")
    branch: bpy.props.StringProperty(name="Branch")

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
    # Refresh change log to show only selected branch
    try:
        refresh_change_log(self)
    except Exception:
        pass


def _on_changes_log_index_update(self, context):
    """When a log item is selected, check out the scene up to that commit."""
    try:
        # Non-blocking best-effort; avoid modal
        bpy.ops.gitblend.checkout_log('EXEC_DEFAULT')
    except Exception:
        pass


class GITBLEND_Properties(bpy.types.PropertyGroup):
    """Root properties for GITBLEND add-on."""
    # Change log
    changes_log: bpy.props.CollectionProperty(type=GITBLEND_ChangeLogEntry)
    changes_log_index: bpy.props.IntProperty(
        default=0,
        update=_on_changes_log_index_update,
        description="Select a log entry to show the scene up to that commit",
    )
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

    # UI toggles for collapsible sections
    ui_show_commit: bpy.props.BoolProperty(
        name="Show Commit",
        default=True,
        description="Expand or collapse the Commit section",
    )
    ui_show_branches: bpy.props.BoolProperty(
        name="Show Branches",
        default=True,
        description="Expand or collapse the Branches section",
    )
    ui_show_log: bpy.props.BoolProperty(
        name="Show Change Log",
        default=True,
        description="Expand or collapse the Change Log section",
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