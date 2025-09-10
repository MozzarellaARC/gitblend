import bpy
from ..utils.validate import (
    ensure_gitblend_collection,
    slugify,
    get_latest_snapshot,
    create_diff_snapshot_with_changes,
    should_skip_commit,
    unique_coll_name,
    list_branch_snapshots_upto_uid,
)
from ..utils.utils import (
    now_str,
    request_redraw,
    get_props,
    get_selected_branch,
    log_change,
    set_dropdown_selection,
    ensure_enum_contains,
    sanitize_save_path,
    build_name_map,
    find_containing_collection,
    path_to_collection,
    ensure_mirrored_path,
    duplicate_object_with_data,
    remove_object_safely,
    remap_scene_pointers,
)
from .index import (
    compute_collection_signature,
    derive_changed_set,
)
from .cas import (
    create_cas_commit,
    get_latest_commit_objects,
    resolve_commit_by_uid,
    list_branch_commits,
    read_commit,
    update_ref,
)


class RestoreOperationMixin:
    """Mixin class providing common restoration functionality."""
    
    def find_snapshot_obj_and_dest(self, nm: str, snap_maps: list, source: bpy.types.Collection):
        """Find object in snapshots and determine destination collection."""
        for root, mp in snap_maps:
            o = mp.get(nm)
            if o is None:
                continue
            cont = find_containing_collection(root, o) or root
            path = path_to_collection(root, cont)
            dest = ensure_mirrored_path(source, path) if path else source
            return o, dest
        return None, source
    
    def restore_objects_from_commit(self, source, commit_objs, snapshots, removed_msg_parts):
        """Common logic for restoring objects from a commit."""
        desired_names = [o.get("name", "") for o in commit_objs if o.get("name")]
        desired_parent = {o.get("name", ""): o.get("parent", "") for o in commit_objs if o.get("name")}

        # Build maps
        src_map = build_name_map(source, snapshot=False)
        snap_maps = [(root, build_name_map(root, snapshot=True)) for root in snapshots]

        # Remove extras
        removed_extras = 0
        for nm, obj in list(src_map.items()):
            if nm not in desired_names:
                if remove_object_safely(obj):
                    removed_extras += 1

        # Rebuild map after removals
        src_map = build_name_map(source, snapshot=False)

        # Restore objects
        new_dups = {}
        old_objs = {}

        for nm in desired_names:
            snap_obj, dest_coll = self.find_snapshot_obj_and_dest(nm, snap_maps, source)
            if not snap_obj:
                continue

            try:
                dup = duplicate_object_with_data(snap_obj)
                # Temporary unique name during wiring; we'll rename after cleanup
                dup.name = f"{nm}_restored"
                # Preserve original base name metadata to aid remapping
                try:
                    dup["gitblend_orig_name"] = nm
                except Exception:
                    pass
            except Exception:
                continue

            curr = src_map.get(nm)
            if curr:
                old_objs[nm] = curr

            # Link duplicate
            linked_any = False
            try:
                dest_coll.objects.link(dup)
                linked_any = True
            except Exception:
                pass

            if not linked_any:
                try:
                    source.objects.link(dup)
                except Exception:
                    pass

            new_dups[nm] = dup

        # Remap pointers BEFORE deleting old ones
        remap_scene_pointers(source, new_dups)

        # Set parents
        for nm, dup in new_dups.items():
            pnm = desired_parent.get(nm, "")
            target_parent = new_dups.get(pnm) or src_map.get(pnm) if pnm else None
            try:
                dup.parent = target_parent
            except Exception:
                pass

        # Clean up old objects in a dependency-safe order: remove those without dependents first
        # Perform a few passes to avoid dependency issues with modifiers/constraints
        remaining = {nm: old_objs[nm] for nm in desired_names if nm in old_objs}
        for _ in range(3):
            if not remaining:
                break
            removed_any = False
            for nm, obj in list(remaining.items()):
                try:
                    # If object has no users in its collections beyond itself, try removing
                    if remove_object_safely(obj):
                        remaining.pop(nm, None)
                        removed_any = True
                except Exception:
                    continue
            if not removed_any:
                # Force remove the rest to avoid leaving duplicates behind
                for nm, obj in list(remaining.items()):
                    try:
                        remove_object_safely(obj)
                    except Exception:
                        pass
                remaining.clear()

        # Rename duplicates
        for nm, dup in new_dups.items():
            try:
                dup.name = nm
            except Exception:
                pass

        # Final pointer remap after renaming to ensure any temporary wiring resolves to final names
        try:
            remap_scene_pointers(source, new_dups)
        except Exception:
            pass

        restored = len(new_dups)
        skipped = max(0, len(desired_names) - restored)

        if removed_extras:
            removed_msg_parts.append(f"removed {removed_extras} extra")

        return restored, skipped


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


class GITBLEND_OT_string_add(bpy.types.Operator):
    bl_idname = "gitblend.string_add"
    bl_label = "Add String Item"
    bl_description = "Add a new item to the string list"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty(name="Branch name", description="Name of the new branch", default="")

    def invoke(self, context, event):
        # Ensure environment is valid before showing prompt
        scene = context.scene
        has_gitblend = (bpy.data.scenes.get("gitblend") or bpy.data.scenes.get(".gitblend")) is not None
        if not has_gitblend:
            self.report({'ERROR'}, "'gitblend' Scene does not exist. Click Initialize first.")
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
        has_gitblend = (bpy.data.scenes.get("gitblend") or bpy.data.scenes.get(".gitblend")) is not None
        if not has_gitblend:
            self.report({'ERROR'}, "'gitblend' Scene does not exist. Click Initialize first.")
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
        # Ensure project is saved in a valid path
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        # Ensure gitblend exists
        dot_scene = bpy.data.scenes.get("gitblend") or bpy.data.scenes.get(".gitblend")
        if not dot_scene:
            self.report({'ERROR'}, "'gitblend' Scene does not exist. Click Initialize first.")
            return {'CANCELLED'}
        dot_coll = dot_scene.collection

        props = get_props(context)
        branch = get_selected_branch(props) if props else "main"

        # Identify last commit (head) from CAS
        commits = list_branch_commits(branch)
        if not commits:
            self.report({'INFO'}, f"No commits found for branch '{branch}'.")
            return {'CANCELLED'}
        # Head commit
        last_id, last_commit = commits[0]
        last_uid = str(last_commit.get('uid', ''))
        snap_name = None
        for c in list(dot_coll.children):
            nm = c.name or ""
            if last_uid and nm.endswith(last_uid):
                snap_name = nm
                break

        # Delete snapshot collection if present
        snap_coll = None
        for c in list(dot_coll.children):
            if c.name == snap_name:
                snap_coll = c
                break
        if snap_coll is not None:
            try:
                # Unlink from parent first
                dot_coll.children.unlink(snap_coll)
            except Exception:
                pass
            try:
                bpy.data.collections.remove(snap_coll, do_unlink=True)
            except Exception:
                # If removal fails, keep going but notify
                self.report({'WARNING'}, f"Snapshot collection '{snap_name}' could not be fully removed.")

        # Move branch ref to parent commit (undo head)
        try:
            c = read_commit(last_id)
            parents = (c.get('parents', []) if c else []) or []
            parent_id = parents[0] if parents else ""
            update_ref(branch, parent_id)
        except Exception:
            pass

        # Pop from UI change log if available (remove most recent entry for this branch)
        if props:
            try:
                # remove last matching branch entry; prefer matching UID
                rm_idx = -1
                for i in range(len(props.changes_log) - 1, -1, -1):
                    e = props.changes_log[i]
                    if (getattr(e, "branch", "") or "").strip() == branch:
                        rm_idx = i
                        if last_uid and getattr(e, "uid", "") == last_uid:
                            break
                if rm_idx >= 0:
                    props.changes_log.remove(rm_idx)
            except Exception:
                pass

        # Optionally restore working collection to the new HEAD commit state
        try:
            # Reconstruct scene to match the latest commit after undo
            bpy.ops.gitblend.discard_changes()
        except Exception:
            pass
        request_redraw()
        self.report({'INFO'}, f"Undid last commit on '{branch}'.")
        return {'FINISHED'}


class GITBLEND_OT_discard_changes(bpy.types.Operator, RestoreOperationMixin):
    bl_idname = "gitblend.discard_changes"
    bl_label = "Discard Changes"
    bl_description = "Restore objects from the latest snapshot back into the working collection (for that branch)"
    bl_options = {'INTERNAL'}

    def _list_branch_snapshots(self, scene, branch):
        """Mirror logic from validate._list_branch_snapshots but locally"""
        from ..utils.validate import _list_branch_snapshots
        return _list_branch_snapshots(scene, branch)

    def execute(self, context):
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        dot_scene = bpy.data.scenes.get("gitblend") or bpy.data.scenes.get(".gitblend")
        if not dot_scene:
            self.report({'ERROR'}, "'gitblend' Scene does not exist. Click Initialize first.")
            return {'CANCELLED'}
        dot_coll = dot_scene.collection

        props = get_props(context)
        branch = get_selected_branch(props) if props else "main"

        # Restore into the scene's root collection
        source = scene.collection

        latest = get_latest_commit_objects(branch)
        if not latest:
            self.report({'INFO'}, f"No commit history for branch '{branch}'.")
            return {'CANCELLED'}
        _cid, _commit, prev_objs = latest
        commit_objs = list(prev_objs.values())
        snapshots = self._list_branch_snapshots(scene, branch)

        removed_msg_parts = []
        restored, skipped = self.restore_objects_from_commit(source, commit_objs, snapshots, removed_msg_parts)

        request_redraw()
        msg = f"Restored {restored} object(s) from snapshot"
        if skipped:
            msg += f", skipped {skipped}"
        if removed_msg_parts:
            msg += f", {', '.join(removed_msg_parts)}"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GITBLEND_OT_checkout_log(bpy.types.Operator, RestoreOperationMixin):
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
        dot_scene = bpy.data.scenes.get("gitblend") or bpy.data.scenes.get(".gitblend")
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