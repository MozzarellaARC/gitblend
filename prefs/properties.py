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
    
    file_size: bpy.props.IntProperty(
        name="File Size",
        description="Size of the commit file in bytes",
        default=0
    )
    
    hash_value: bpy.props.StringProperty(
        name="Hash Value",
        description="SHA-256 hash of the commit content",
        default=""
    )

def commit_selection_update(self, context):
    """Callback function that triggers checkout when selection changes"""
    # Only trigger checkout if we have commits and a valid selection
    if len(self.commit_history) > 0 and 0 <= self.i < len(self.commit_history):
        # Automatically trigger checkout
        bpy.ops.gitblend.checkout()

class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_history: bpy.props.CollectionProperty(
        type=GITBLEND_CommitItem,
        name="Commit History",
        description="List of all commits"
    )
    
    i: bpy.props.IntProperty(
        name="Active Commit Index",
        description="Index of the active commit in the list",
        default=0,
        update=commit_selection_update
    )