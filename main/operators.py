import bpy
from .validate import (
    ensure_gitblend_collection,
    get_dotgitblend_collection,
    slugify,
    get_latest_snapshot,
    create_diff_snapshot_with_changes,
    should_skip_commit,
    unique_coll_name,
    list_branch_snapshots,
    SnapshotManager,
)
from .utils import (
    now_str,
    request_redraw,
    get_props,
    get_selected_branch,
    ensure_source_collection,
    log_change,
    set_dropdown_selection,
    ensure_enum_contains,
    sanitize_save_path,
    refresh_change_log,
)
from .index import (
    load_index,
    save_index,
    compute_collection_signature,
    update_index_with_commit,
    derive_changed_set,
    get_latest_commit,
)


class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Copy the 'source' working collection into .gitblend as a snapshot named with the branch/message; log the message"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        props = get_props(context)
        if not props:
            self.report({'ERROR'}, "GITBLEND properties not found")
            return {'CANCELLED'}

        msg = (props.commit_message or "").strip()
        if not msg:
            self.report({'ERROR'}, "Please enter a commit message before committing.")
            return {'CANCELLED'}

        scene = context.scene

        # Require a valid saved file path (not drive root)
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        sel = get_selected_branch(props) or "main"
        msg_slug = slugify(msg)
        # Snapshot base name still includes branch/message, but working coll stays 'source'
        snapshot_base_name = f"{sel}-{msg_slug}" if msg_slug else sel

        # Always operate on a working collection named 'source'
        source = ensure_source_collection(scene)
        if not source:
            self.report({'WARNING'}, "No top-level collection to commit")
            return {'CANCELLED'}

        # Never rename the working collection; keep it as 'source'

        # Require existing .gitblend created via Initialize
        dot_coll = get_dotgitblend_collection(scene)
        if not dot_coll:
            self.report({'ERROR'}, "'.gitblend' collection does not exist. Click Initialize first.")
            return {'CANCELLED'}

        # Snapshot-based validation for early skip (keeps logic consistent with validator)
        skip, reason = should_skip_commit(scene, source, sel)
        if skip:
            self.report({'INFO'}, f"No changes detected; skipping snapshot ({reason})")
            return {'CANCELLED'}

        uid = now_str("%Y%m%d%H%M%S")

        prev = get_latest_snapshot(scene, sel)

        # Differential snapshot: compute changed set via index signatures to be robust to previous diff snapshots
        index = load_index()
        last = get_latest_commit(index, sel)
        changed_names = None
        curr_sigs = None
        curr_coll_hash = None
        if last:
            # Build prev objs dict from last commit entries
            prev_objs = {o.get("name", ""): o for o in (last.get("objects", []) or []) if o.get("name")}
            curr_sigs, curr_coll_hash = compute_collection_signature(source)
            changed, names = derive_changed_set(curr_sigs, prev_objs)
            changed_names = set(names) if changed else set()
        # Create diff snapshot using computed changed set (or let it compute if None)
        # Create diff snapshot with names derived from snapshot_base_name while leaving working coll as 'source'
        new_coll, obj_map = create_diff_snapshot_with_changes(source, dot_coll, uid, prev, changed_names=changed_names)
        # Rename snapshot collection to follow our branch/message naming convention (ensure unique)
        try:
            desired = unique_coll_name(snapshot_base_name, uid)
            new_coll.name = desired
        except Exception:
            pass

        # Update index (stored as JSON)
        snapshot_name = new_coll.name
        # Compute signatures to record exact state (reuse if already computed)
        if curr_sigs is None or curr_coll_hash is None:
            obj_sigs, coll_hash = compute_collection_signature(source)
        else:
            obj_sigs, coll_hash = curr_sigs, curr_coll_hash
        index = load_index()
        index = update_index_with_commit(index, sel, uid, now_str(), msg, snapshot_name, obj_sigs, coll_hash)
        save_index(index)

        log_change(props, msg)
        # Rebuild branch-specific log
        try:
            refresh_change_log(props)
        except Exception:
            pass
        props.commit_message = ""
        request_redraw()

        self.report({'INFO'}, "Commit snapshot created in .gitblend")
        return {'FINISHED'}


class GITBLEND_OT_initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Create .gitblend; ensure a 'source' working collection exists; create the first snapshot"
    bl_options = {'INTERNAL'}  # exclude from undo/redo and search

    def execute(self, context):
        # Require the .blend file to be saved and not at drive root
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        # Ensure a sensible default commit message on first run
        props = get_props(context)
        if props and not (props.commit_message or "").strip():
            props.commit_message = "Initialize"
        # Ensure the default/selected branch exists in the enum and is selected
        if props:
            branch = (getattr(props, "gitblend_branch", "") or "main").strip() or "main"
            ensure_enum_contains(props, branch)
            # Select the branch we just ensured exists
            try:
                idx = next((i for i, it in enumerate(props.string_items) if (it.name or "").strip().lower() == branch.lower()), -1)
            except Exception:
                idx = -1
            if idx >= 0:
                set_dropdown_selection(props, idx)
            request_redraw()
        # Ensure .gitblend exists up-front for user feedback in UI
        ensure_gitblend_collection(context.scene)
        # Ensure a working 'source' collection is present
        try:
            ensure_source_collection(context.scene)
        except Exception:
            pass
        # Delegate to the Commit operator; first commit will initialize automatically
        return bpy.ops.gitblend.commit()


class GITBLEND_OT_string_add(bpy.types.Operator):
    bl_idname = "gitblend.string_add"
    bl_label = "Add String Item"
    bl_description = "Add a new item to the string list"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty(name="Branch name", description="Name of the new branch", default="")

    def invoke(self, context, event):
        # Ensure environment is valid before showing prompt
        scene = context.scene
        has_gitblend = get_dotgitblend_collection(scene) is not None
        if not has_gitblend:
            self.report({'ERROR'}, "'.gitblend' collection does not exist. Click Initialize first.")
            return {'CANCELLED'}

        # Pre-fill a reasonable default
        props = get_props(context)
        if props and not (self.name or "").strip():
            base = (props.gitblend_branch or "branch").strip() or "branch"
            # Make it look unique-ish for convenience
            self.name = f"{base}-{len(props.string_items)+1}"
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name", text="Branch name")

    def execute(self, context):
        props = get_props(context)
        if not props:
            self.report({'ERROR'}, "GITBLEND properties not found")
            return {'CANCELLED'}
        # Require existing .gitblend collection
        scene = context.scene
        has_gitblend = get_dotgitblend_collection(scene) is not None
        if not has_gitblend:
            self.report({'ERROR'}, "'.gitblend' collection does not exist. Click Initialize first.")
            return {'CANCELLED'}

        nm = (self.name or "").strip()
        if not nm:
            self.report({'ERROR'}, "Please enter a branch name.")
            return {'CANCELLED'}
        # Avoid duplicates (case-insensitive)
        if any((it.name or "").strip().lower() == nm.lower() for it in props.string_items):
            self.report({'ERROR'}, f"Branch '{nm}' already exists.")
            return {'CANCELLED'}

        item = props.string_items.add()
        item.name = nm
        set_dropdown_selection(props, len(props.string_items) - 1)
        request_redraw()
        return {'FINISHED'}


class GITBLEND_OT_string_remove(bpy.types.Operator):
    bl_idname = "gitblend.string_remove"
    bl_label = "Remove String Item"
    bl_description = "Remove the selected item from the string list"
    bl_options = {'INTERNAL'}
    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        props = get_props(context)
        if not props:
            self.report({'ERROR'}, "GITBLEND properties not found")
            return {'CANCELLED'}
        idx = self.index if self.index >= 0 else props.string_items_index
        if 0 <= idx < len(props.string_items):
            props.string_items.remove(idx)
            set_dropdown_selection(props, idx)
            request_redraw()
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No item selected")
            return {'CANCELLED'}

class GITBLEND_OT_undo_commit(bpy.types.Operator):
    bl_idname = "gitblend.undo_commit"
    bl_label = "Undo Last Commit"
    bl_description = "Remove the latest commit for the selected branch and delete its snapshot"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # Validate environment
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        # Check for .gitblend collection
        dot_coll = get_dotgitblend_collection(scene)
        if not dot_coll:
            self.report({'ERROR'}, "'.gitblend' collection does not exist. Click Initialize first.")
            return {'CANCELLED'}

        props = get_props(context)
        branch = get_selected_branch(props) if props else "main"

        index = load_index()
        b = (index.get("branches", {})).get(branch)
        if not b or not b.get("commits"):
            self.report({'INFO'}, f"No commits found for branch '{branch}'.")
            return {'CANCELLED'}

        commits = b.get("commits", [])
        last = commits[-1]
        snap_name = last.get("snapshot", "")

        # Delete snapshot collection if present
        snap_coll = None
        for c in list(dot_coll.children):
            if c.name == snap_name:
                snap_coll = c
                break
        if snap_coll is not None:
            try:
                dot_coll.children.unlink(snap_coll)
            except Exception:
                pass
            try:
                bpy.data.collections.remove(snap_coll, do_unlink=True)
            except Exception:
                self.report({'WARNING'}, f"Snapshot collection '{snap_name}' could not be fully removed.")

        # Update index
        commits.pop()
        if commits:
            prev = commits[-1]
            b["head"] = {
                "uid": prev.get("uid", ""),
                "snapshot": prev.get("snapshot", ""),
                "timestamp": prev.get("timestamp", ""),
            }
        else:
            b["head"] = {}

        save_index(index)

        # Update UI change log by refreshing from index
        if props:
            try:
                refresh_change_log(props)
            except Exception:
                pass

        # Restore to new HEAD state
        try:
            remaining_commits = (b.get("commits", []) if b else [])
            if remaining_commits:
                bpy.ops.gitblend.discard_changes()
        except Exception:
            pass
        
        request_redraw()
        self.report({'INFO'}, f"Undid last commit on '{branch}'.")
        return {'FINISHED'}


class GITBLEND_OT_discard_changes(bpy.types.Operator):
    bl_idname = "gitblend.discard_changes"
    bl_label = "Discard Changes"
    bl_description = "Restore objects from the latest snapshot back into the working collection (for that branch)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # Validate environment
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        # Check .gitblend collection
        dot_coll = get_dotgitblend_collection(scene)
        if not dot_coll:
            self.report({'ERROR'}, "'.gitblend' collection does not exist. Click Initialize first.")
            return {'CANCELLED'}

        props = get_props(context)
        branch = get_selected_branch(props) if props else "main"

        # Get source collection
        source = ensure_source_collection(scene)
        if not source:
            self.report({'WARNING'}, "No top-level collection to restore into.")
            return {'CANCELLED'}

        # Load latest commit data
        index = load_index()
        last = get_latest_commit(index, branch)
        if not last:
            self.report({'INFO'}, f"No commit history for branch '{branch}'.")
            return {'CANCELLED'}

        # Get desired object state
        commit_objs = last.get("objects", []) or []
        
        # Get snapshot collections for restoration
        snapshots = list_branch_snapshots(scene, branch)
        
        # Use SnapshotManager to restore objects
        restored, skipped, removed = SnapshotManager.restore_objects_from_snapshots(
            commit_objs, source, snapshots
        )

        request_redraw()
        msg = f"Restored {restored} object(s) from snapshot"
        if skipped:
            msg += f", skipped {skipped}"
        if removed:
            msg += f", removed {removed} extra"
        self.report({'INFO'}, msg)
        # Log view may not change, but ensure consistency if timestamps/messages updated
        try:
            props = get_props(context)
            if props:
                refresh_change_log(props)
        except Exception:
            pass
        return {'FINISHED'}


class GITBLEND_OT_checkout_log(bpy.types.Operator):
    bl_idname = "gitblend.checkout_log"
    bl_label = "Checkout Log Entry"
    bl_description = "Restore the working collection to the state up to the selected log entry"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # Validate environment
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        # Check .gitblend collection
        dot_coll = get_dotgitblend_collection(scene)
        if not dot_coll:
            self.report({'ERROR'}, "'.gitblend' collection does not exist. Click Initialize first.")
            return {'CANCELLED'}

        props = get_props(context)
        branch = get_selected_branch(props) if props else "main"

        # Load commits and resolve target from UI selection
        index = load_index()
        b = (index.get("branches", {})).get(branch) or {}
        commits = b.get("commits", []) or []
        if not commits:
            self.report({'INFO'}, f"No commit history for branch '{branch}'.")
            return {'CANCELLED'}

        # Get target commit from UI selection
        ui_idx = getattr(props, "changes_log_index", 0) if props else 0
        ui_idx = max(0, min(ui_idx, len(commits) - 1))
        target = commits[ui_idx]
        target_uid = str(target.get("uid", ""))

        if not target_uid:
            self.report({'WARNING'}, "Selected log entry has no UID; cannot checkout.")
            return {'CANCELLED'}

        # Get source collection
        source = ensure_source_collection(scene)
        if not source:
            self.report({'WARNING'}, "No top-level collection to restore into.")
            return {'CANCELLED'}

        # Get desired object state from target commit
        commit_objs = target.get("objects", []) or []
        
        # Get snapshots up to target UID
        snapshots = list_branch_snapshots(scene, branch, max_uid=target_uid)
        
        # Use SnapshotManager to restore objects
        restored, skipped, removed = SnapshotManager.restore_objects_from_snapshots(
            commit_objs, source, snapshots
        )

        request_redraw()
        msg = f"Checked out commit {ui_idx+1}/{len(commits)}"
        commit_msg = (target.get("message", "") or "").strip()
        if commit_msg:
            msg += f": {commit_msg}"
        if skipped:
            msg += f" (skipped {skipped})"
        if removed:
            msg += f", removed {removed} extra"
        self.report({'INFO'}, msg)
        # Ensure log selection aligns with UI index
        try:
            props = get_props(context)
            if props:
                refresh_change_log(props)
        except Exception:
            pass
        return {'FINISHED'}

def register_operators():
    bpy.utils.register_class(GITBLEND_OT_commit)
    bpy.utils.register_class(GITBLEND_OT_initialize)
    bpy.utils.register_class(GITBLEND_OT_string_add)
    bpy.utils.register_class(GITBLEND_OT_string_remove)
    bpy.utils.register_class(GITBLEND_OT_undo_commit)
    bpy.utils.register_class(GITBLEND_OT_discard_changes)
    bpy.utils.register_class(GITBLEND_OT_checkout_log)


def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_discard_changes)
    bpy.utils.unregister_class(GITBLEND_OT_undo_commit)
    bpy.utils.unregister_class(GITBLEND_OT_string_remove)
    bpy.utils.unregister_class(GITBLEND_OT_string_add)
    bpy.utils.unregister_class(GITBLEND_OT_initialize)
    bpy.utils.unregister_class(GITBLEND_OT_commit)
    try:
        bpy.utils.unregister_class(GITBLEND_OT_checkout_log)
    except RuntimeError:
        pass
