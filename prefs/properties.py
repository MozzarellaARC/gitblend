"""Properties for git_blend data."""
import bpy
from bpy.props import CollectionProperty, StringProperty, IntProperty, FloatProperty


def on_commit_selection_change(self, context):
    """Callback when commit selection changes - automatically checkout the selected commit."""
    if hasattr(context.scene, 'gitblend') and context.scene.gitblend.commits:
        active_index = context.scene.gitblend.active_commit_index
        if 0 <= active_index < len(context.scene.gitblend.commits):
            selected_commit = context.scene.gitblend.commits[active_index]
            # Only checkout if it's not already the current commit
            if not selected_commit.is_current:
                try:
                    bpy.ops.gitblend.checkout(commit_hash=selected_commit.hash)
                    # Refresh the commit list to update current status
                    bpy.ops.gitblend.refresh_commits()
                except:
                    # Handle any errors silently
                    pass


class GITBLEND_CommitItem(bpy.types.PropertyGroup):
    """Property group for individual commit items."""
    hash: StringProperty(name="Hash")
    message: StringProperty(name="Message")
    timestamp: StringProperty(name="Timestamp")
    timestamp_float: FloatProperty(name="Timestamp Float")  # For sorting
    is_current: bpy.props.BoolProperty(name="Is Current", default=False)


class GITBLEND_Properties(bpy.types.PropertyGroup):
    """Main property group for git_blend."""
    commits: CollectionProperty(type=GITBLEND_CommitItem, name="Commits")
    active_commit_index: IntProperty(
        name="Active Commit Index", 
        default=-1,
        update=on_commit_selection_change
    )
    commit_message: StringProperty(
        name="Commit Message",
        description="Message for the next commit",
        default="Update blend file",
        maxlen=256
    )
    
    
def register_properties():
    bpy.utils.register_class(GITBLEND_CommitItem)
    bpy.utils.register_class(GITBLEND_Properties)
    bpy.types.Scene.gitblend = bpy.props.PointerProperty(type=GITBLEND_Properties)


def unregister_properties():
    del bpy.types.Scene.gitblend
    bpy.utils.unregister_class(GITBLEND_Properties)
    bpy.utils.unregister_class(GITBLEND_CommitItem)