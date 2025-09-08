import bpy # type: ignore


class GITBLEND_ChangeLogEntry(bpy.types.PropertyGroup):
    """Single commit/change-log entry."""
    timestamp: bpy.props.StringProperty(name="Timestamp")
    message: bpy.props.StringProperty(name="Message")
    branch: bpy.props.StringProperty(name="Branch", default="")
    uid: bpy.props.StringProperty(name="UID", default="")

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

    # IO / Append (for headless or UI-driven append)
    ui_show_io: bpy.props.BoolProperty(
        name="Show Append/IO",
        default=False,
        description="Expand or collapse the Append/IO section",
    )
    io_base_blend: bpy.props.StringProperty(
        name="Base .blend",
        description="Optional base .blend to open first (headless workflows)",
        subtype='FILE_PATH',
        default="",
    )
    io_source_blend: bpy.props.StringProperty(
        name="Source .blend",
        description="Path to the .blend file to append from",
        subtype='FILE_PATH',
        default="",
    )
    io_object_names: bpy.props.StringProperty(
        name="Objects",
        description="Comma-separated object names to append",
        default="",
    )
    io_collection: bpy.props.StringProperty(
        name="Collection",
        description="Destination collection (created if needed). Leave empty to use Scene collection",
        default="",
    )
    io_save_as: bpy.props.StringProperty(
        name="Save As",
        description="Optional output .blend path. Leave empty to save in place",
        subtype='FILE_PATH',
        default="",
    )


