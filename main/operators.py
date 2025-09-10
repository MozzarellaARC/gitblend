import bpy

from ..utils.utils import (
    request_redraw,
    get_props,
    get_selected_branch,
    set_dropdown_selection,
    sanitize_save_path,
    build_name_map,
    find_containing_collection,
    path_to_collection,
    ensure_mirrored_path,
    duplicate_object_with_data,
    remove_object_safely,
    remap_scene_pointers,
)

from .cas import (
    create_cas_commit,
    get_latest_commit_objects,
    resolve_commit_by_uid,
    list_branch_commits,
    read_commit,
    update_ref,
)

from ..prefs.properties import SCENE_DIR, HIDDEN_SCENE_DIR


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
        # Collect desired collection path segment names from commit object metadata so we can prune stale collections
        desired_collection_names = set()
        for co in commit_objs:
            cp = co.get("collection_path", "") or ""
            if not cp:
                continue
            for seg in cp.split("|"):
                if seg:
                    desired_collection_names.add(seg)

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

        # -----------------------------
        # Prune now-empty collections not present in the target commit
        # -----------------------------
        def prune_empty_collections(parent_coll):
            removed = 0
            # Work on a static list since we may unlink during iteration
            for child in list(parent_coll.children):
                removed += prune_empty_collections(child)
                # Skip if child still has children or objects
                if child.objects or child.children:
                    continue
                # Keep collection if its name is part of desired collection path set
                # (intermediate path segments or leaf collections that still exist logically)
                if child.name in desired_collection_names:
                    continue
                # Unlink from all parents that reference it (defensive: though typical hierarchy has one parent)
                try:
                    for uc in list(child.users_collection):
                        try:
                            uc.children.unlink(child)
                        except Exception:
                            pass
                except Exception:
                    pass
                # Remove the collection datablock
                try:
                    bpy.data.collections.remove(child, do_unlink=True)
                    removed += 1
                except Exception:
                    # If removal fails, ignore and continue
                    pass
            return removed

        pruned_count = prune_empty_collections(source)
        if pruned_count:
            removed_msg_parts.append(f"removed {pruned_count} collection{'s' if pruned_count != 1 else ''}")

        return restored, skipped

class GITBLEND_OT_string_add(bpy.types.Operator):
    bl_idname = "gitblend.string_add"
    bl_label = "Add String Item"
    bl_description = "Add a new item to the string list"
    bl_options = {'INTERNAL'}

    name: bpy.props.StringProperty(name="Branch name", description="Name of the new branch", default="")

    def invoke(self, context, event):
        # Ensure environment is valid before showing prompt
        scene = context.scene
        has_gitblend = (bpy.data.scenes.get(SCENE_DIR) or bpy.data.scenes.get(HIDDEN_SCENE_DIR)) is not None
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
        has_gitblend = (bpy.data.scenes.get(SCENE_DIR) or bpy.data.scenes.get(HIDDEN_SCENE_DIR)) is not None
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
        # Validate environment
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        # Ensure gitblend exists
        dot_scene = bpy.data.scenes.get(SCENE_DIR) or bpy.data.scenes.get(HIDDEN_SCENE_DIR)
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
                dot_coll.children.unlink(snap_coll)
            except Exception:
                pass
            try:
                bpy.data.collections.remove(snap_coll, do_unlink=True)
            except Exception:
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

        # Restore to new HEAD state
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
        dot_scene = bpy.data.scenes.get(SCENE_DIR) or bpy.data.scenes.get(HIDDEN_SCENE_DIR)
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





