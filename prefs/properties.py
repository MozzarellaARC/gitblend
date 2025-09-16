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
            # Cancel any pending branch switch timer
            if hasattr(self, '_pending_branch_switch_timer'):
                try:
                    bpy.app.timers.unregister(self._pending_branch_switch_timer)
                except ValueError:
                    pass
            
            # Defer the branch switch to avoid context issues
            def _deferred_switch():
                try:
                    # Double-check if switch is still needed
                    current_branch_check = get_current_branch(project_dir)
                    if self.branch_enum == current_branch_check:
                        return None
                    
                    bpy.ops.gitblend.switch_branch(branch_name=self.branch_enum)
                    # Refresh branch commits after switching
                    from ..main.initialize import populate_branch_commits
                    populate_branch_commits(bpy.context, self.branch_enum)
                except Exception as e:
                    print(f'[gitblend] Branch switch failed: {e}')
                finally:
                    # Clear the timer reference
                    if hasattr(self, '_pending_branch_switch_timer'):
                        delattr(self, '_pending_branch_switch_timer')
                return None
            
            # Store timer reference for potential cancellation
            self._pending_branch_switch_timer = _deferred_switch
            bpy.app.timers.register(_deferred_switch, first_interval=0.1)
    except Exception:
        pass


# Global cache for branch items to avoid excessive disk reads
_branch_items_cache = {
    'items': [("main", "main", "Default branch")],
    'last_update': 0,
    'project_dir': None
}


def _get_branch_items(self, context):
    """Generate items for branch enum property with caching."""
    global _branch_items_cache
    
    try:
        blend_path = bpy.data.filepath
        if not blend_path:
            return [("main", "main", "Default branch")]
        
        from pathlib import Path
        from ..main.initialize import is_gitblend_initialized, get_branch_names
        import time
        
        project_dir = Path(blend_path).resolve().parent
        if not is_gitblend_initialized(project_dir):
            return [("main", "main", "Default branch")]
        
        current_time = time.time()
        
        # Use cache if:
        # 1. Same project directory
        # 2. Cache is less than 1 second old
        if (_branch_items_cache['project_dir'] == str(project_dir) and 
            current_time - _branch_items_cache['last_update'] < 1.0):
            return _branch_items_cache['items']
        
        # Refresh cache
        branch_names = get_branch_names(project_dir)
        if not branch_names:
            items = [("main", "main", "Default branch")]
        else:
            items = [(name, name, f"Branch: {name}") for name in sorted(branch_names)]
        
        # Update cache
        _branch_items_cache['items'] = items
        _branch_items_cache['last_update'] = current_time
        _branch_items_cache['project_dir'] = str(project_dir)
        
        return items
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
    except Exception:
        return
    
    if self.branch_commits_index < 0 or self.branch_commits_index >= len(self.branch_commits):
        return

    # Get the actual commit hash to find the index in all commits
    selected_branch_commit = self.branch_commits[self.branch_commits_index]
    target_hash = selected_branch_commit.hash
    
    # Check if we're already on this commit to avoid unnecessary checkout
    current_hash = ""
    try:
        if self.commits_index >= 0 and self.commits_index < len(self.commits):
            current_hash = self.commits[self.commits_index].hash
    except (IndexError, AttributeError):
        pass
    
    if current_hash == target_hash:
        return  # Already on this commit, no need to checkout
    
    # Find this commit in the full commits list
    target_index = -1
    for i, commit in enumerate(self.commits):
        if commit.hash == target_hash:
            target_index = i
            break
    
    if target_index < 0:
        return
    
    # Cancel any pending checkout timer to prevent conflicts
    if hasattr(self, '_pending_branch_checkout_timer'):
        try:
            bpy.app.timers.unregister(self._pending_branch_checkout_timer)
        except ValueError:
            pass
    
    # Update the main commits_index to stay in sync (without triggering callback)
    wm['gitblend_loading_history'] = True
    try:
        self.commits_index = target_index
    finally:
        if 'gitblend_loading_history' in wm:
            del wm['gitblend_loading_history']

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
                # Clear the timer reference
                if hasattr(self, '_pending_branch_checkout_timer'):
                    delattr(self, '_pending_branch_checkout_timer')
            except Exception:
                pass
        return None  # Do not repeat

    # Store timer reference for potential cancellation
    self._pending_branch_checkout_timer = _deferred
    bpy.app.timers.register(_deferred, first_interval=0.1)


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
        if context.scene.name == "_stash":
            return
    except Exception:
        return
        
    if self.commits_index < 0 or self.commits_index >= len(self.commits):
        return

    # Check if we're already on this commit to avoid unnecessary checkout
    target_hash = self.commits[self.commits_index].hash
    
    # Check current scene state or other indicators to see if we're already on this commit
    # This helps prevent redundant checkouts
    current_scene_name = context.scene.name
    
    # Cancel any pending checkout timer to prevent conflicts
    if hasattr(self, '_pending_main_checkout_timer'):
        try:
            bpy.app.timers.unregister(self._pending_main_checkout_timer)
        except ValueError:
            pass

    # Update the branch commit index to stay in sync (without triggering callback)
    wm = context.window_manager
    wm['gitblend_loading_history'] = True
    try:
        # Find matching commit in branch_commits and update index
        for i, branch_commit in enumerate(self.branch_commits):
            if branch_commit.hash == target_hash:
                self.branch_commits_index = i
                break
    finally:
        if 'gitblend_loading_history' in wm:
            del wm['gitblend_loading_history']

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
                # Clear the timer reference
                if hasattr(self, '_pending_main_checkout_timer'):
                    delattr(self, '_pending_main_checkout_timer')
            except Exception:
                pass
        return None  # Do not repeat

    # Store timer reference for potential cancellation
    self._pending_main_checkout_timer = _deferred
    bpy.app.timers.register(_deferred, first_interval=0.1)


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