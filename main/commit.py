import bpy  # type: ignore

# Refactored imports: functions were split between utils.utils, utils.validate, index, and cas.
from ..utils.utils import (
    get_props,
    sanitize_save_path,
    get_selected_branch,
    now_str,
    log_change,
    set_dropdown_selection,
    ensure_enum_contains,
    request_redraw,
)
from ..utils.validate import (
    slugify,
    unique_coll_name,
    should_skip_commit,
    create_diff_snapshot_with_changes,
    get_latest_snapshot,
    get_latest_commit_objects,
    ensure_gitblend_collection,
)
from .index import (
    compute_collection_signature,
    derive_changed_set,
)
from .cas import (
    create_cas_commit,
)

from ..prefs.properties import SCENE_DIR, HIDDEN_SCENE_DIR


class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Copy the scene's root collection into gitblend as a snapshot named with the branch/message; log the message"
    # Removed 'UNDO' so this operator never pushes an undo step (we also return FINISHED on success)
    bl_options = {'REGISTER'}

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
        # Snapshot base name still includes branch/message
        snapshot_base_name = f"{sel}-{msg_slug}" if msg_slug else sel

        # Use the scene's root collection as the working area
        source = scene.collection

        # Require existing gitblend Scene created via Initialize
        dot_scene = bpy.data.scenes.get(SCENE_DIR) or bpy.data.scenes.get(HIDDEN_SCENE_DIR)
        if not dot_scene:
            self.report({'ERROR'}, "'gitblend' Scene does not exist. Click Initialize first.")
            return {'CANCELLED'}
        dot_coll = dot_scene.collection

        # Snapshot-based validation for early skip (keeps logic consistent with validator)
        skip, reason = should_skip_commit(scene, source, sel)
        if skip:
            self.report({'INFO'}, f"No changes detected; skipping snapshot ({reason})")
            return {'CANCELLED'}

        uid = now_str("%Y%m%d%H%M%S")

        prev = get_latest_snapshot(scene, sel)

        # Differential snapshot: compute changed set using CAS head commit objects
        changed_names = None
        try:
            latest = get_latest_commit_objects(sel)
        except Exception:
            latest = None
        if latest:
            _cid, _commit, prev_objs = latest
            curr_sigs, _coll_hash = compute_collection_signature(source)
            changed, names = derive_changed_set(curr_sigs, prev_objs)
            changed_names = set(names) if changed else set()

        # Create diff snapshot using computed changed set (or let it compute if None)
        new_coll, obj_map = create_diff_snapshot_with_changes(source, dot_coll, uid, prev, changed_names=changed_names)
        # Rename snapshot collection to follow our branch/message naming convention (ensure unique)
        try:
            desired = unique_coll_name(snapshot_base_name, uid)
            new_coll.name = desired
        except Exception:
            pass

        # CAS-only path: compute signatures and write CAS commit; index.json is deprecated
        snapshot_name = new_coll.name
        obj_sigs, _coll_hash = compute_collection_signature(source)
        try:
            create_cas_commit(sel, uid, now_str(), msg, obj_sigs)
        except Exception:
            pass

        # Record UI log entry with branch and uid for filtering/selection
        try:
            log_change(props, msg, branch=sel)
            if len(props.changes_log) > 0:
                props.changes_log[-1].uid = uid
        except Exception:
            pass
        props.commit_message = ""
        request_redraw()
        self.report({'INFO'}, "Commit snapshot created in gitblend")
        return {'FINISHED'}


class GITBLEND_OT_initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Create gitblend; ensure a 'source' working collection exists; create the first snapshot"
    # No UNDO: initialization should not create an undo entry
    bl_options = {'REGISTER'}  # exclude from undo/redo stack

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
        # Detect existing gitblend scene -> sync mode instead of forcing new commit
        existing_scene = bpy.data.scenes.get(SCENE_DIR) or bpy.data.scenes.get(HIDDEN_SCENE_DIR)
        if existing_scene is not None:
            # Sync: rebuild branches list from refs, and rebuild change log for selected branch
            if props:
                try:
                    # Clear current branch list (string_items)
                    while len(props.string_items) > 0:
                        props.string_items.remove(0)
                except Exception:
                    pass
                # Discover branches from refs directory (.gitblend/refs/heads)
                try:
                    import os
                    from .cas import get_store_root, list_branch_commits
                    heads_dir = os.path.join(get_store_root(), "refs", "heads")
                    branch_names = []
                    if os.path.isdir(heads_dir):
                        for fn in os.listdir(heads_dir):
                            if fn.startswith('.'):
                                continue
                            branch_names.append(fn)
                    # Always ensure at least 'main'
                    if not branch_names:
                        branch_names = [getattr(props, "gitblend_branch", "main") or "main"]
                    for b in sorted(set(branch_names)):
                        ensure_enum_contains(props, b)
                    # Select current stored branch or first
                    desired = (getattr(props, "gitblend_branch", "") or "").strip()
                    if not desired or desired not in { (it.name or "") for it in props.string_items }:
                        desired = branch_names[0]
                    try:
                        sel_idx = next((i for i, it in enumerate(props.string_items) if (it.name or "") == desired), 0)
                    except Exception:
                        sel_idx = 0
                    set_dropdown_selection(props, sel_idx)
                    # Rebuild change log for selected branch from CAS commits
                    try:
                        # Clear change log
                        while len(props.changes_log) > 0:
                            props.changes_log.remove(0)
                    except Exception:
                        pass
                    active_branch = desired
                    try:
                        commits = list_branch_commits(active_branch)
                    except Exception:
                        commits = []
                    for cid, c in reversed(commits):  # old->new so UI index 0 becomes latest when selecting
                        try:
                            entry = props.changes_log.add()
                            entry.timestamp = c.get("timestamp", "")
                            entry.message = c.get("message", "")
                            entry.branch = active_branch
                            entry.uid = c.get("uid", "")
                        except Exception:
                            pass
                except Exception:
                    pass
                request_redraw()
            self.report({'INFO'}, "gitblend scene exists; project synchronized (branches and log rebuilt)")
            return {'FINISHED'}

        # Fresh initialization path: create scene and perform initial commit
        ensure_gitblend_collection(context.scene)
        if props:
            branch = (getattr(props, "gitblend_branch", "") or "main").strip() or "main"
            ensure_enum_contains(props, branch)
            try:
                idx = next((i for i, it in enumerate(props.string_items) if (it.name or "").strip().lower() == branch.lower()), -1)
            except Exception:
                idx = -1
            if idx >= 0:
                set_dropdown_selection(props, idx)
        request_redraw()
        # Return underlying commit result (expected to be {'FINISHED'} on success now)
        return bpy.ops.gitblend.commit()