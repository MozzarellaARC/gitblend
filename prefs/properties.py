import bpy

class GITBLEND_CommitItem(bpy.types.PropertyGroup):
    message: bpy.props.StringProperty(
        name="Message",
        description="Commit message",
        default=""
    )
    
    timestamp: bpy.props.StringProperty(
        name="Timestamp",
        description="Commit timestamp",
        default=""
    )
    
    uid: bpy.props.StringProperty(
        name="UID",
        description="Unique identifier for the commit",
        default=""
    )
    
    filename: bpy.props.StringProperty(
        name="Filename",
        description="Blend file name for this commit",
        default=""
    )

class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_history: bpy.props.CollectionProperty(
        type=GITBLEND_CommitItem,
        name="Commit History",
        description="List of all commits"
    )
    
    commit_history_index: bpy.props.IntProperty(
        name="Active Commit Index",
        description="Index of the active commit in the list",
        default=0
    )