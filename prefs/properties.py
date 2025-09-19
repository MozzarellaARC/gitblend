import bpy  # type: ignore


def update_commit_history(self, context):
    """Update callback to refresh commit history when needed"""
    try:
        from ..main.initialize import populate_commit_history
        populate_commit_history(context)
    except Exception:
        pass  # Silently fail to avoid breaking the UI


class GITBLEND_CommitEntry(bpy.types.PropertyGroup):
    hash: bpy.props.StringProperty(name="Hash", default="")
    message: bpy.props.StringProperty(name="Message", default="")
    timestamp: bpy.props.StringProperty(name="Timestamp", default="")


class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_message: bpy.props.StringProperty(
        name="Commit Message",
        description="Message for the commit",
        default=""
    )
    initialized: bpy.props.BoolProperty(
        name="Initialized",
        description="Whether Git Blend has been initialized in this project",
        default=False,
        update=update_commit_history
    )
    
    # Commit history
    commits: bpy.props.CollectionProperty(type=GITBLEND_CommitEntry)
    commits_index: bpy.props.IntProperty(default=0)
    
    # Auto-refresh trigger
    refresh_history: bpy.props.BoolProperty(
        name="Refresh History",
        description="Trigger to refresh commit history",
        default=False,
        update=update_commit_history
    )