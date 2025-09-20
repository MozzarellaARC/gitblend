"""Properties for git_blend data."""
import bpy
from bpy.props import CollectionProperty, StringProperty, IntProperty


class GITBLEND_CommitItem(bpy.types.PropertyGroup):
    """Property group for individual commit items."""
    hash: StringProperty(name="Hash")
    message: StringProperty(name="Message")
    timestamp: StringProperty(name="Timestamp")
    is_current: bpy.props.BoolProperty(name="Is Current", default=False)


class GITBLEND_Properties(bpy.types.PropertyGroup):
    """Main property group for git_blend."""
    commits: CollectionProperty(type=GITBLEND_CommitItem, name="Commits")
    active_commit_index: IntProperty(name="Active Commit Index", default=-1)
    
    
def register_properties():
    bpy.utils.register_class(GITBLEND_CommitItem)
    bpy.utils.register_class(GITBLEND_Properties)
    bpy.types.Scene.gitblend = bpy.props.PointerProperty(type=GITBLEND_Properties)


def unregister_properties():
    del bpy.types.Scene.gitblend
    bpy.utils.unregister_class(GITBLEND_Properties)
    bpy.utils.unregister_class(GITBLEND_CommitItem)