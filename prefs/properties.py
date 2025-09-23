import bpy

def preview_update_callback(self, context):
    """Callback function when preview checkbox is toggled"""
    if self.is_previewed:
        # Clear any existing previews first
        from ..main.checkout import cleanup_temp_objects
        cleanup_temp_objects()
        
        # Clear other commit preview checkboxes (only one preview at a time)
        scene = context.scene.gitblend_props
        for commit in scene.commit_history:
            if commit != self and commit.is_previewed:
                commit.is_previewed = False
        
        # Trigger pre-checkout for this commit
        # We need to temporarily set the active index to this commit's index
        commit_history = scene.commit_history
        
        # Find the index of this commit item
        commit_index = -1
        for i, commit in enumerate(commit_history):
            if commit == self:
                commit_index = i
                break
        
        if commit_index >= 0:
            # Temporarily set the active index
            old_index = scene.i
            scene.i = commit_index
            
            # Trigger pre-checkout
            try:
                bpy.ops.gitblend.pre_checkout()
            except Exception as e:
                print(f"Error during pre-checkout: {e}")
                # Reset checkbox on error
                self.is_previewed = False
            
            # Restore the old index
            scene.i = old_index
    else:
        # Clear preview objects when unchecked
        from ..main.checkout import cleanup_temp_objects
        cleanup_temp_objects()

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
    
    is_previewed: bpy.props.BoolProperty(
        name="Preview",
        description="Preview this commit (loads objects with _temp suffix)",
        default=False,
        update=lambda self, context: preview_update_callback(self, context)
    )

def commit_selection_update(self, context):
    """Callback function when selection changes - no longer auto-triggers pre-checkout"""
    # Selection changed - user can manually use checkbox for preview
    pass

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