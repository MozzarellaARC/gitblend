import bpy
from bpy.props import (
    StringProperty,
    CollectionProperty,
    IntProperty,
)

class GITBLEND_CommitItem(bpy.types.PropertyGroup):
    """Individual commit item for UIList"""
    message: StringProperty(
        name="Message",
        description="Commit message",
        default=""
    )
    
    timestamp: StringProperty(
        name="Timestamp",
        description="Commit timestamp",
        default=""
    )
    
    uid: StringProperty(
        name="UID",
        description="Unique identifier for the commit",
        default=""
    )
    
    filename: StringProperty(
        name="Filename",
        description="Blend file name for this commit",
        default=""
    )

class GITBLEND_Properties(bpy.types.PropertyGroup):
    message: StringProperty(
        name="Commit Message",
        description="Message for the commit",
        default="Commit Message",
        maxlen=64
    )
    
    commit_history: CollectionProperty(
        type=GITBLEND_CommitItem,
        name="Commit History",
        description="List of all commits"
    )
    
    commit_history_index: IntProperty(
        name="Active Commit Index",
        description="Index of the active commit in the list",
        default=0
    )