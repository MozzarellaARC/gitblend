import bpy
from ..utils import (get_props, sanitize_save_path, get_selected_branch,
                    slugify, now_str, should_skip_commit,
                    unique_coll_name, compute_collection_signature,
                    derive_changed_set, create_diff_snapshot_with_changes,
                    create_cas_commit, log_change,
                    set_dropdown_selection, ensure_enum_contains,
                    request_redraw)

from ..utils.validate import (get_latest_snapshot, 
                              get_latest_commit_objects,
                              ensure_gitblend_collection
                              )

class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Copy the scene's root collection into gitblend as a snapshot named with the branch/message; log the message"
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
        # Snapshot base name still includes branch/message
        snapshot_base_name = f"{sel}-{msg_slug}" if msg_slug else sel

        # Use the scene's root collection as the working area
        source = scene.collection

        # Require existing gitblend Scene created via Initialize
        dot_scene = bpy.data.scenes.get("gitblend") or bpy.data.scenes.get(".gitblend")
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
        # Ensure gitblend (Scene) exists up-front for user feedback in UI
        ensure_gitblend_collection(context.scene)
        # Delegate to the Commit operator; first commit will initialize automatically
        return bpy.ops.gitblend.commit()