import bpy # type: ignore
import os
import time
from ..utils.git_utils import is_repo, get_log, get_current_branch
_GB_LOG_CACHE = {"path": "", "entries": [], "ts": 0.0}


def _get_cached_log(repo_path: str, max_count: int = 15, ttl_sec: float = 2.0):
    now = time.time()
    global _GB_LOG_CACHE
    if _GB_LOG_CACHE["path"] != repo_path or (now - _GB_LOG_CACHE["ts"]) > ttl_sec:
        _GB_LOG_CACHE["entries"] = get_log(repo_path, max_count=max_count)
        _GB_LOG_CACHE["path"] = repo_path
        _GB_LOG_CACHE["ts"] = now
    return _GB_LOG_CACHE["entries"]

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

        current_file = bpy.data.filepath
        if not current_file:
            # Show init action even before saving; operator will prompt/error if needed
            col.operator("gitblend.init", text="Initialize Git Blend", icon='FILE_NEW')
            col.label(text="Save your .blend to enable commit & history", icon='ERROR')
            return
        working_root = os.path.dirname(current_file)
        dot_gitblend = os.path.join(working_root, '.gitblend')

        if not is_repo(dot_gitblend):
            # Always show a button: use commit as the initializer fallback
            col.operator("gitblend.commit", text="Initialize Git Blend", icon='FILE_NEW')
            col.label(text=f"Repo: {dot_gitblend}")
            return

        # Repo exists: message input, commit action and recent commits
        row = col.row(align=True)
        row.prop(context.scene, "gitblend_commit_message", text="Message")
        commits = _get_cached_log(dot_gitblend, max_count=15)
        if not commits:
            col.operator("gitblend.commit", text="Initialize Git Blend", icon='FILE_TICK')
        else:
            col.operator("gitblend.commit", text="Commit Scene", icon='FILE_TICK')

        box = layout.box()
        box.label(text="Recent Commits", icon='TEXT')
        branch = get_current_branch(dot_gitblend) or ""
        if not commits:
            box.label(text=f"{branch} No commits yet.")
        else:
            for c in commits:
                row = box.row(align=True)
                row.label(text=c.get('date', ''))
                row.label(text=branch)
                row.label(text=c.get('subject', ''))