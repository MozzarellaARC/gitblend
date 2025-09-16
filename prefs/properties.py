import bpy  # type: ignore
from bpy.types import PropertyGroup
import functools


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
                _perform_checkout(bpy.context, target_index)
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