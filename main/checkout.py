import bpy

# Corrected imports: commit/branch history helpers live in cas.py; snapshot listing stays in validate.
from ..utils.validate import (
    list_branch_snapshots_upto_uid,
)
from ..utils.utils import (
    get_props,
    get_selected_branch,
    sanitize_save_path,
    request_redraw,
)
from .cas import (
    list_branch_commits,
    resolve_commit_by_uid,
)

from .operators import RestoreOperationMixin

from ..prefs.properties import SCENE_DIR, HIDDEN_SCENE_DIR


class GITBLEND_OT_checkout(bpy.types.Operator, RestoreOperationMixin):
    bl_idname = "gitblend.checkout_log"
    bl_label = "Checkout Log Entry"
    bl_description = "Restore the working collection to the state up to the selected log entry"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        dot_scene = bpy.data.scenes.get(SCENE_DIR) or bpy.data.scenes.get(HIDDEN_SCENE_DIR)
        if not dot_scene:
            self.report({'ERROR'}, "'gitblend' Scene does not exist. Click Initialize first.")
            return {'CANCELLED'}
        dot_coll = dot_scene.collection

        props = get_props(context)
        branch = get_selected_branch(props) if props else "main"

        commits = list_branch_commits(branch)
        if not commits:
            self.report({'INFO'}, f"No commit history for branch '{branch}'.")
            return {'CANCELLED'}

        # Map selection via UI list to the actual selected change log entry
        target_uid = ""
        try:
            if props and 0 <= props.changes_log_index < len(props.changes_log):
                selected = props.changes_log[props.changes_log_index]
                if (getattr(selected, "branch", "") or "").strip() == branch:
                    target_uid = getattr(selected, "uid", "") or ""
        except Exception:
            target_uid = ""
        # Fallback to latest commit uid
        if not target_uid and commits:
            target_uid = commits[0][1].get("uid", "")
        if not target_uid:
            self.report({'WARNING'}, "Unable to resolve target commit UID.")
            return {'CANCELLED'}
        # Find the target commit by uid
        resolved = resolve_commit_by_uid(branch, target_uid)
        if not resolved:
            self.report({'WARNING'}, "Selected commit not found in index.")
            return {'CANCELLED'}
        target_id, target = resolved

        # Restore into the scene's root collection
        source = scene.collection

        tree_id = target.get("tree", "")
        if not tree_id:
            self.report({'WARNING'}, "Target commit lacks tree reference.")
            return {'CANCELLED'}
        from .cas import flatten_tree_to_objects
        commit_map = flatten_tree_to_objects(tree_id)
        commit_objs = list(commit_map.values())
        snapshots = list_branch_snapshots_upto_uid(scene, branch, target_uid)

        removed_msg_parts = []
        restored, skipped = self.restore_objects_from_commit(source, commit_objs, snapshots, removed_msg_parts)

        request_redraw()
        # Derive position for messaging
        try:
            pos = next((i for i, (_id, c) in enumerate(commits) if str(c.get("uid", "")) == str(target_uid)), -1)
        except Exception:
            pos = -1
        msg = f"Checked out commit {pos+1 if pos>=0 else '?'}/{len(commits)}"
        m = (target.get("message", "") or "").strip()
        if m:
            msg += f": {m}"
        if skipped:
            msg += f" (skipped {skipped})"
        if removed_msg_parts:
            msg += f", {', '.join(removed_msg_parts)}"
        self.report({'INFO'}, msg)
        return {'FINISHED'}