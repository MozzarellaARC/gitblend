import bpy # type: ignore
import os
import time
from ..utils.git_utils import is_repo, get_log, get_current_branch
from ..utils.validation import require_saved_blend, get_dot_gitblend
_GB_LOG_CACHE = {"path": "", "entries": [], "ts": 0.0}
_GB_BRANCH_CACHE = {"path": "", "branch": "", "ts": 0.0}


def _get_cached_log(repo_path: str, max_count: int = 15, ttl_sec: float = 3600.0):
    now = time.time()
    global _GB_LOG_CACHE
    if _GB_LOG_CACHE["path"] != repo_path or (now - _GB_LOG_CACHE["ts"]) > ttl_sec:
        _GB_LOG_CACHE["entries"] = get_log(repo_path, max_count=max_count)
        _GB_LOG_CACHE["path"] = repo_path
        _GB_LOG_CACHE["ts"] = now
    return _GB_LOG_CACHE["entries"]


def _get_cached_branch(repo_path: str, ttl_sec: float = 3600.0):
    now = time.time()
    global _GB_BRANCH_CACHE
    if _GB_BRANCH_CACHE["path"] != repo_path or (now - _GB_BRANCH_CACHE["ts"]) > ttl_sec:
        _GB_BRANCH_CACHE["branch"] = get_current_branch(repo_path) or ""
        _GB_BRANCH_CACHE["path"] = repo_path
        _GB_BRANCH_CACHE["ts"] = now
    return _GB_BRANCH_CACHE["branch"]


def _force_refresh(repo_path: str):
    global _GB_LOG_CACHE, _GB_BRANCH_CACHE
    _GB_LOG_CACHE["path"] = ""
    _GB_LOG_CACHE["ts"] = 0.0
    _GB_BRANCH_CACHE["path"] = ""
    _GB_BRANCH_CACHE["ts"] = 0.0


class GITBLEND_OT_refresh(bpy.types.Operator):
    bl_idname = "gitblend.refresh"
    bl_label = "Refresh Git Blend"
    bl_description = "Refresh Git Blend caches"

    def execute(self, context):
        try:
            working_root = require_saved_blend(context)
        except Exception:
            return {'CANCELLED'}
        dot_gitblend = get_dot_gitblend(working_root)
        _force_refresh(dot_gitblend)
        # Best effort redraw
        try:
            for window in bpy.context.window_manager.windows:  # type: ignore[attr-defined]
                screen = window.screen
                for area in screen.areas:
                    area.tag_redraw()
        except Exception:
            pass
        self.report({'INFO'}, 'Git Blend view refreshed')
        return {'FINISHED'}

class GITBLEND_Panel(bpy.types.Panel):
    bl_idname = "GB_PT_main_panel"
    bl_label = "Git Blend"
    bl_category = "Git Blend"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        try:
            working_root = require_saved_blend(context)
        except Exception:
            # Require saving before enabling Git Blend features
            col.label(text="Save your .blend to enable Git Blend", icon='ERROR')
            return
        dot_gitblend = get_dot_gitblend(working_root)

        if not is_repo(dot_gitblend):
            # Always show a button: use commit as the initializer fallback
            col.operator("gitblend.commit", text="Initialize Git Blend", icon='FILE_NEW')
            col.label(text=f"Repo: {dot_gitblend}")
            return

        # Repo exists: message input, commit action and recent commits
        row = col.row(align=True)
        row.prop(context.scene, "gitblend_commit_message", text="Message")

        header = col.row(align=True)
        header.operator("gitblend.refresh", text="Refresh", icon='FILE_REFRESH')

        commits = _get_cached_log(dot_gitblend, max_count=15)
        has_msg = bool((getattr(context.scene, 'gitblend_commit_message', '') or '').strip())
        if not commits:
            b = col.operator("gitblend.commit", text="Initialize Git Blend", icon='FILE_TICK')
            b.enabled = has_msg
        else:
            b = col.operator("gitblend.commit", text="Commit Scene", icon='FILE_TICK')
            b.enabled = has_msg

        box = layout.box()
        box.label(text="Recent Commits", icon='TEXT')
        branch = _get_cached_branch(dot_gitblend) or ""
        if not commits:
            box.label(text=f"{branch} No commits yet.")
        else:
            for c in commits:
                row = box.row(align=True)
                row.label(text=c.get('date', ''))
                row.label(text=branch)
                row.label(text=c.get('subject', ''))