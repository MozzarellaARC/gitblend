import bpy
from .validate import (
    ensure_gitblend_collection,
    slugify,
    get_latest_snapshot,
    create_diff_snapshot_with_changes,
    should_skip_commit,
)
from .utils import (
    now_str,
    request_redraw,
    get_props,
    get_selected_branch,
    find_preferred_or_first_non_dot,
    log_change,
    set_dropdown_selection,
    ensure_enum_contains,
    sanitize_save_path,
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
    bl_description = "Rename the source collection to the selected prefix and copy it into .gitblend with a UID suffix; log the message"
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
        base_name = f"{sel}-{msg_slug}" if msg_slug else sel

        source = find_preferred_or_first_non_dot(scene, base_name)
        if not source:
            self.report({'WARNING'}, "No top-level collection to commit")
            return {'CANCELLED'}

        if source.name != base_name:
            other = bpy.data.collections.get(base_name)
            if other and other is not source:
                source = other
            else:
                try:
                    source.name = base_name
                except Exception:
                    pass

        # Require existing .gitblend created via Initialize
        dot_coll = None
        for c in scene.collection.children:
            if c.name == ".gitblend":
                dot_coll = c
                break
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
        if last:
            # Build prev objs dict from last commit entries
            prev_objs = {o.get("name", ""): o for o in (last.get("objects", []) or []) if o.get("name")}
            curr_sigs, _coll_hash = compute_collection_signature(source)
            changed, names = derive_changed_set(curr_sigs, prev_objs)
            changed_names = set(names) if changed else set()
        # Create diff snapshot using computed changed set (or let it compute if None)
        new_coll, obj_map = create_diff_snapshot_with_changes(source, dot_coll, uid, prev, changed_names=changed_names)

        # Update TOML index
        snapshot_name = new_coll.name
        # Compute signatures after snapshot to record exact state
        obj_sigs, coll_hash = compute_collection_signature(source)
        index = load_index()
        index = update_index_with_commit(index, sel, uid, now_str(), msg, snapshot_name, obj_sigs, coll_hash)
        save_index(index)

        log_change(props, msg)
        props.commit_message = ""
        request_redraw()

        self.report({'INFO'}, "Commit snapshot created in .gitblend")
        return {'FINISHED'}


class GITBLEND_OT_initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Create .gitblend; rename source to preferred root name; copy it into .gitblend with a UID suffix"
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
        has_gitblend = any(c.name == ".gitblend" for c in scene.collection.children)
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
        has_gitblend = any(c.name == ".gitblend" for c in scene.collection.children)
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
        # Ensure project is saved in a valid path
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        # Ensure .gitblend exists
        dot_coll = None
        for c in scene.collection.children:
            if c.name == ".gitblend":
                dot_coll = c
                break
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
                # Unlink from parent first
                dot_coll.children.unlink(snap_coll)
            except Exception:
                pass
            try:
                bpy.data.collections.remove(snap_coll, do_unlink=True)
            except Exception:
                # If removal fails, keep going but notify
                self.report({'WARNING'}, f"Snapshot collection '{snap_name}' could not be fully removed.")

        # Pop the commit and rewind head
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
        request_redraw()
        self.report({'INFO'}, f"Undid last commit on '{branch}'.")
        return {'FINISHED'}


class GITBLEND_OT_discard_changes(bpy.types.Operator):
    bl_idname = "gitblend.discard_changes"
    bl_label = "Discard Changes"
    bl_description = "Restore objects from the latest snapshot back into the working collection (for that branch)"
    bl_options = {'INTERNAL'}

    def _iter_objects_recursive(self, coll):
        for o in coll.objects:
            yield o
        for c in coll.children:
            yield from self._iter_objects_recursive(c)

    def _orig_name(self, id_block):
        # Prefer stored original name, else strip trailing _<uid>[-i]
        try:
            v = id_block.get("gitblend_orig_name", None)
            if isinstance(v, str) and v:
                return v
        except Exception:
            pass
        name = getattr(id_block, "name", "") or ""
        # Strip _<digits> or _<digits>-<digits> suffix
        import re
        m = re.search(r"_(\d{10,20})(?:-\d+)?$", name)
        return name[: m.start()] if m else name

    def _build_name_map(self, coll, snapshot=False):
        out = {}
        for o in self._iter_objects_recursive(coll):
            nm = self._orig_name(o) if snapshot else (o.name or "")
            if nm and nm not in out:
                out[nm] = o
        return out

    def execute(self, context):
        # Ensure project is saved in a valid path
        ok, _proj, err = sanitize_save_path()
        if not ok:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        scene = context.scene
        # Ensure .gitblend exists
        dot_coll = None
        for c in scene.collection.children:
            if c.name == ".gitblend":
                dot_coll = c
                break
        if not dot_coll:
            self.report({'ERROR'}, "'.gitblend' collection does not exist. Click Initialize first.")
            return {'CANCELLED'}

        props = get_props(context)
        branch = get_selected_branch(props) if props else "main"

        # Find source working collection (prefer branch name)
        source = find_preferred_or_first_non_dot(scene, branch)
        if not source:
            self.report({'WARNING'}, "No top-level collection to restore into.")
            return {'CANCELLED'}

        # Find latest snapshot for this branch
        snapshot = get_latest_snapshot(scene, branch)
        if not snapshot:
            self.report({'INFO'}, f"No snapshot found for branch '{branch}'.")
            return {'CANCELLED'}

        # Build maps
        snap_map = self._build_name_map(snapshot, snapshot=True)
        src_map = self._build_name_map(source, snapshot=False)

        if not snap_map:
            self.report({'INFO'}, "Latest snapshot has no objects to restore.")
            return {'CANCELLED'}

        # Limit restore set to objects that exist in both snapshot and working set
        names_to_restore = sorted(set(snap_map.keys()) & set(src_map.keys()))
        skipped = len(set(snap_map.keys()) - set(names_to_restore))

        # First pass: create duplicates and link to same collections, keep mapping
        new_dups = {}
        old_objs = {}
        parent_names = {}
        for name in names_to_restore:
            snap_obj = snap_map[name]
            curr = src_map.get(name)
            if not curr:
                continue
            old_objs[name] = curr
            parent_names[name] = curr.parent.name if curr.parent else None
            try:
                dup = snap_obj.copy()
                if getattr(snap_obj, "data", None) is not None:
                    try:
                        dup.data = snap_obj.data.copy()
                    except Exception:
                        pass
            except Exception:
                continue
            # Temporary unique-ish name to avoid clashes
            tmp_name = f"{name}_restored"
            try:
                dup.name = tmp_name
            except Exception:
                pass
            # Link to all collections where the current object exists
            try:
                colls = list(curr.users_collection)
            except Exception:
                colls = []
            linked_any = False
            for col in colls:
                try:
                    col.objects.link(dup)
                    linked_any = True
                except Exception:
                    pass
            if not linked_any:
                try:
                    source.objects.link(dup)
                except Exception:
                    pass
            new_dups[name] = dup

        # Second pass: set parenting to corresponding restored parents where possible
        for name, dup in list(new_dups.items()):
            pnm = parent_names.get(name)
            if not pnm:
                # Ensure no parent
                try:
                    dup.parent = None
                except Exception:
                    pass
                continue
            new_parent = new_dups.get(pnm)
            if new_parent is not None:
                try:
                    dup.parent = new_parent
                except Exception:
                    pass
            else:
                # Keep existing parent (still the current object) until we remove; then it will become None
                try:
                    dup.parent = old_objs.get(name).parent
                except Exception:
                    pass

        # Third pass: remove old objects
        for name in names_to_restore:
            curr = old_objs.get(name)
            if not curr:
                continue
            try:
                colls = list(curr.users_collection)
            except Exception:
                colls = []
            for col in colls:
                try:
                    col.objects.unlink(curr)
                except Exception:
                    pass
            try:
                bpy.data.objects.remove(curr, do_unlink=True)
            except Exception:
                pass

        # Final pass: rename dups to original names
        for name, dup in list(new_dups.items()):
            try:
                dup.name = name
            except Exception:
                pass

        restored = len(new_dups)

        request_redraw()
        msg = f"Restored {restored} object(s) from snapshot"
        if skipped:
            msg += f", skipped {skipped}"
        self.report({'INFO'}, msg)
        return {'FINISHED'}

def register_operators():
    bpy.utils.register_class(GITBLEND_OT_commit)
    bpy.utils.register_class(GITBLEND_OT_initialize)
    bpy.utils.register_class(GITBLEND_OT_string_add)
    bpy.utils.register_class(GITBLEND_OT_string_remove)
    bpy.utils.register_class(GITBLEND_OT_undo_commit)
    bpy.utils.register_class(GITBLEND_OT_discard_changes)


def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_discard_changes)
    bpy.utils.unregister_class(GITBLEND_OT_undo_commit)
    bpy.utils.unregister_class(GITBLEND_OT_string_remove)
    bpy.utils.unregister_class(GITBLEND_OT_string_add)
    bpy.utils.unregister_class(GITBLEND_OT_initialize)
    bpy.utils.unregister_class(GITBLEND_OT_commit)
