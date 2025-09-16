import bpy  # type: ignore
from bpy.types import PropertyGroup
import functools


def _branch_switch_update(self, context):
    """Handle branch selection change."""
    try:
        # Don't switch if we're loading or in an operation
        wm = context.window_manager
        if (wm.get('gitblend_loading_history') or 
            wm.get('gitblend_doing_checkout') or 
            wm.get('gitblend_commit_in_progress') or
            wm.get('gitblend_stash_in_progress') or
            wm.get('gitblend_branch_in_progress')):
            return
        
        # Check if the selected branch is different from current
        blend_path = bpy.data.filepath
        if not blend_path:
            return
        
        from pathlib import Path
        from ..main.initialize import get_current_branch
        
        project_dir = Path(blend_path).resolve().parent
        current_branch = get_current_branch(project_dir)
        
        if self.branch_enum != current_branch:
            # Defer the branch switch to avoid context issues
            def _deferred_switch():
                try:
                    bpy.ops.gitblend.switch_branch(branch_name=self.branch_enum)
                    # Refresh branch commits after switching
                    from ..main.initialize import populate_branch_commits
                    populate_branch_commits(bpy.context, self.branch_enum)
                except Exception as e:
                    print(f'[gitblend] Branch switch failed: {e}')
                return None
            
            bpy.app.timers.register(_deferred_switch, first_interval=0.05)
    except Exception:
        pass


def _get_branch_items(self, context):
    """Generate items for branch enum property."""
    try:
        blend_path = bpy.data.filepath
        if not blend_path:
            return [("main", "main", "Default branch")]
        
        from pathlib import Path
        from ..main.initialize import is_gitblend_initialized, get_branch_names
        
        project_dir = Path(blend_path).resolve().parent
        if not is_gitblend_initialized(project_dir):
            return [("main", "main", "Default branch")]
        
        branch_names = get_branch_names(project_dir)
        if not branch_names:
            return [("main", "main", "Default branch")]
        
        return [(name, name, f"Branch: {name}") for name in sorted(branch_names)]
    except Exception:
        return [("main", "main", "Default branch")]


def _auto_checkout_branch_update(self, context):  # noqa: D401
    """When user changes branch commit selection, defer checkout via timer to ensure valid context."""
    try:
        wm = context.window_manager  # type: ignore
        # Suppression flags - prevent auto-checkout during other operations
        if (wm.get('gitblend_loading_history') or 
            wm.get('gitblend_doing_checkout') or 
            wm.get('gitblend_commit_in_progress') or
            wm.get('gitblend_stash_in_progress')):
            return
        
        # Don't auto-checkout if _stash scene exists and is active
        if context.scene.name == "_stash":
            return
            
        # Check if _stash scene exists - might indicate ongoing stash operations
        if "_stash" in bpy.data.scenes:
            pass
            
    except Exception:
        return
    
    if self.branch_commits_index < 0 or self.branch_commits_index >= len(self.branch_commits):
        return

    # Get the actual commit hash to find the index in all commits
    selected_branch_commit = self.branch_commits[self.branch_commits_index]
    target_hash = selected_branch_commit.hash
    
    # Find this commit in the full commits list
    target_index = -1
    for i, commit in enumerate(self.commits):
        if commit.hash == target_hash:
            target_index = i
            break
    
    if target_index < 0:
        return
    
    # Update the main commits_index to stay in sync
    self.commits_index = target_index

    def _deferred():
        try:
            wm = bpy.context.window_manager  # type: ignore
            # Double-check suppression flags in deferred context
            if (wm.get('gitblend_loading_history') or 
                wm.get('gitblend_commit_in_progress') or
                wm.get('gitblend_stash_in_progress')):
                return None  # retry next heartbeat
            wm['gitblend_doing_checkout'] = True
            # Directly call internal helper to avoid operator poll/context constraints
            try:
                from ..main.checkout import _perform_checkout  # type: ignore
                success = _perform_checkout(bpy.context, target_index)
                if success:
                    # Update branch status after successful checkout
                    try:
                        from ..main.initialize import update_branch_status
                        update_branch_status(bpy.context)
                    except Exception:
                        pass
            except Exception as e:  # pragma: no cover
                print('[gitblend] Auto-checkout failed:', e)
        finally:
            try:
                if 'gitblend_doing_checkout' in bpy.context.window_manager:  # type: ignore
                    del bpy.context.window_manager['gitblend_doing_checkout']  # type: ignore
            except Exception:
                pass
        return None  # Do not repeat

    bpy.app.timers.register(_deferred, first_interval=0.05)


def _auto_checkout_update(self, context):  # noqa: D401
    """When user changes selection, defer checkout via timer to ensure valid context."""
    try:
        wm = context.window_manager  # type: ignore
        # Suppression flags - prevent auto-checkout during other operations
        if (wm.get('gitblend_loading_history') or 
            wm.get('gitblend_doing_checkout') or 
            wm.get('gitblend_commit_in_progress') or
            wm.get('gitblend_stash_in_progress')):
            return
        
        # Don't auto-checkout if _stash scene exists and is active
        # This prevents interference with stash operations
        if context.scene.name == "_stash":
            return
            
        # Check if _stash scene exists - might indicate ongoing stash operations
        if "_stash" in bpy.data.scenes:
            # Allow auto-checkout but be more cautious
            pass
            
    except Exception:
        return
    if self.commits_index < 0 or self.commits_index >= len(self.commits):
        return

    # Defer actual operation to a timer so we can build a proper override context
    target_index = int(self.commits_index)

    def _deferred():
        try:
            wm = bpy.context.window_manager  # type: ignore
            # Double-check suppression flags in deferred context
            if (wm.get('gitblend_loading_history') or 
                wm.get('gitblend_commit_in_progress') or
                wm.get('gitblend_stash_in_progress')):
                return None  # retry next heartbeat
            wm['gitblend_doing_checkout'] = True
            # Directly call internal helper to avoid operator poll/context constraints
            try:
                from ..main.checkout import _perform_checkout  # type: ignore
                success = _perform_checkout(bpy.context, target_index)
                if success:
                    # Update branch status after successful checkout
                    try:
                        from ..main.initialize import update_branch_status
                        update_branch_status(bpy.context)
                    except Exception:
                        pass
            except Exception as e:  # pragma: no cover
                print('[gitblend] Auto-checkout failed:', e)
        finally:
            try:
                if 'gitblend_doing_checkout' in bpy.context.window_manager:  # type: ignore
                    del bpy.context.window_manager['gitblend_doing_checkout']  # type: ignore
            except Exception:
                pass
        return None  # Do not repeat

    bpy.app.timers.register(_deferred, first_interval=0.05)


class GITBLEND_CommitEntry(PropertyGroup):
    hash: bpy.props.StringProperty(name="Hash", default="")  # type: ignore
    message: bpy.props.StringProperty(name="Message", default="")  # type: ignore
    timestamp: bpy.props.StringProperty(name="Timestamp", default="")  # type: ignore


class GITBLEND_StashEntry(PropertyGroup):
    """Property group for tracking stashed objects."""
    uid: bpy.props.StringProperty(name="UID", default="")  # type: ignore
    original_names: bpy.props.StringProperty(name="Original Names", default="")  # type: ignore
    stashed_names: bpy.props.StringProperty(name="Stashed Names", default="")  # type: ignore
    timestamp: bpy.props.StringProperty(name="Timestamp", default="")  # type: ignore


class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_message: bpy.props.StringProperty(  # type: ignore
        name="Message",
        description="Commit message",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )
    commits: bpy.props.CollectionProperty(type=GITBLEND_CommitEntry)  # type: ignore
    commits_index: bpy.props.IntProperty(  # type: ignore
        name="Active Commit",
        default=-1,
        update=_auto_checkout_update,
    )
    # Branch-filtered commits for display (updated when branch changes)
    branch_commits: bpy.props.CollectionProperty(type=GITBLEND_CommitEntry)  # type: ignore
    branch_commits_index: bpy.props.IntProperty(  # type: ignore
        name="Active Branch Commit",
        default=-1,
        update=_auto_checkout_branch_update,
    )
    stashed_objects: bpy.props.CollectionProperty(type=GITBLEND_StashEntry)  # type: ignore
    stashed_objects_index: bpy.props.IntProperty(  # type: ignore
        name="Active Stash",
        default=-1,
    )
    show_stash_section: bpy.props.BoolProperty(  # type: ignore
        name="Show Stash Section",
        description="Show/hide the stash section",
        default=True,
    )
    show_repository_section: bpy.props.BoolProperty(  # type: ignore
        name="Show Repository Section",
        description="Show/hide the repository setup section",
        default=True,
    )
    show_history_section: bpy.props.BoolProperty(  # type: ignore
        name="Show History Section",
        description="Show/hide the commit history section",
        default=True,
    )
    # Branch-related properties
    branch_enum: bpy.props.EnumProperty(  # type: ignore
        name="Branch",
        description="Select branch",
        items=_get_branch_items,
        update=_branch_switch_update,
    )
    branch_name: bpy.props.StringProperty(  # type: ignore
        name="Branch Name",
        description="Name for new branch",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )
    current_branch_display: bpy.props.StringProperty(  # type: ignore
        name="Current Branch",
        description="Display current branch name",
        default="main",
    )
    is_on_head: bpy.props.BoolProperty(  # type: ignore
        name="Is on HEAD",
        description="Whether currently on HEAD commit",
        default=True,
    )