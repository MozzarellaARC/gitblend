import bpy  # type: ignore
from bpy.types import PropertyGroup

def _auto_checkout_update(self, context):  # noqa: D401
    """When user changes selection, defer checkout via timer to ensure valid context."""
    try:
        wm = context.window_manager  # type: ignore
        # Suppression flags
        if wm.get('gitblend_loading_history') or wm.get('gitblend_doing_checkout'):
            return
    except Exception:
        return
    if self.commits_index < 0 or self.commits_index >= len(self.commits):
        return

    # Defer actual operation to a timer so we can build a proper override context
    target_index = int(self.commits_index)

    def _deferred():
        try:
            wm = bpy.context.window_manager  # type: ignore
            if wm.get('gitblend_loading_history'):
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
    name: bpy.props.StringProperty(name="Name", default="")  # type: ignore
    original: bpy.props.StringProperty(name="Original Name", default="")  # type: ignore


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
    stash_show: bpy.props.BoolProperty(  # type: ignore
        name="Show Stash",
        description="Expand/collapse the stash section",
        default=False,
    )