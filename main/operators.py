import bpy
from .validate import (
    ensure_gitblend_collection,
    slugify,
    get_latest_snapshot,
    create_diff_snapshot_with_changes,
    should_skip_commit,
    unique_coll_name,
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

        # Pop from UI change log if available (remove most recent entry)
        props = get_props(context)
        if props:
            try:
                if len(props.changes_log) > 0:
                    props.changes_log.remove(len(props.changes_log) - 1)
            except Exception:
                pass

        # Optionally restore working collection to the new HEAD commit state
        try:
            remaining_commits = (b.get("commits", []) if b else [])
            if remaining_commits:
                # Reconstruct scene to match the latest commit after undo
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

    def _list_branch_snapshots(self, scene, branch):
        # Mirror logic from validate._list_branch_snapshots but locally
        dot = None
        for c in scene.collection.children:
            if c.name == ".gitblend":
                dot = c
                break
        if not dot:
            return []
        import re
        uid_re = re.compile(r"_(\d{10,20})(?:-\d+)?$")
        items = []
        for c in dot.children:
            nm = c.name or ""
            if not nm.startswith(branch):
                continue
            m = uid_re.search(nm)
            uid = m.group(1) if m else ""
            if not uid:
                continue
            items.append((uid, c))
        items.sort(key=lambda t: t[0], reverse=True)
        return [c for _, c in items]

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

        # Always restore into the working 'source' collection
        source = ensure_source_collection(scene)
        if not source:
            self.report({'WARNING'}, "No top-level collection to restore into.")
            return {'CANCELLED'}

        # Load index and resolve last commit full object set
        index = load_index()
        last = get_latest_commit(index, branch)
        if not last:
            self.report({'INFO'}, f"No commit history for branch '{branch}'.")
            return {'CANCELLED'}
        commit_objs = last.get("objects", []) or []
        desired_names = [o.get("name", "") for o in commit_objs if o.get("name")]
        desired_parent = {o.get("name", ""): o.get("parent", "") for o in commit_objs if o.get("name")}

        # Prepare source maps
        src_map = self._build_name_map(source, snapshot=False)

        # Build snapshot search list newest->oldest
        snapshots = self._list_branch_snapshots(scene, branch)
        # Couple each root with its name->object map
        snap_maps = [(root, self._build_name_map(root, snapshot=True)) for root in snapshots]

        def _orig_coll_name(coll):
            try:
                v = coll.get("gitblend_orig_name", None)
                if isinstance(v, str) and v:
                    return v
            except Exception:
                pass
            nm = coll.name or ""
            import re
            m = re.search(r"_(\d{10,20})(?:-\d+)?$", nm)
            return nm[: m.start()] if m else nm

        def _find_containing_collection(root_coll, target_obj):
            if target_obj in root_coll.objects:
                return root_coll
            for child in root_coll.children:
                found = _find_containing_collection(child, target_obj)
                if found:
                    return found
            return None

        def _path_to_collection(root_coll, target_coll):
            path = []
            found = False
            def dfs(c, acc):
                nonlocal path, found
                if found:
                    return
                acc.append(c)
                if c == target_coll:
                    path = list(acc)
                    found = True
                else:
                    for ch in c.children:
                        dfs(ch, acc)
                        if found:
                            break
                acc.pop()
            dfs(root_coll, [])
            return path if found else []

        def _ensure_mirrored_path_under_source(source_coll, snapshot_path):
            dest = source_coll
            for snap_coll in snapshot_path[1:]:
                name = _orig_coll_name(snap_coll)
                existing = None
                for ch in dest.children:
                    if ch.name == name:
                        existing = ch
                        break
                if existing is None:
                    try:
                        newc = bpy.data.collections.new(name)
                        dest.children.link(newc)
                        dest = newc
                    except Exception:
                        # If creation fails, fallback to current dest
                        pass
                    else:
                        dest = newc
                else:
                    dest = existing
            return dest

        def find_snapshot_obj_and_dest(nm: str):
            for root, mp in snap_maps:
                o = mp.get(nm)
                if o is None:
                    continue
                cont = _find_containing_collection(root, o) or root
                path = _path_to_collection(root, cont)
                dest = _ensure_mirrored_path_under_source(source, path) if path else source
                return o, dest
            return None, source

        # Remove any objects not part of the committed set
        removed_extras = 0
        for nm, obj in list(src_map.items()):
            if nm not in desired_names:
                try:
                    # Unlink from all collections and remove
                    for col in list(obj.users_collection):
                        try:
                            col.objects.unlink(obj)
                        except Exception:
                            pass
                    bpy.data.objects.remove(obj, do_unlink=True)
                    removed_extras += 1
                except Exception:
                    pass

        # Rebuild map after removals
        src_map = self._build_name_map(source, snapshot=False)

        # First pass: create or replace all desired objects from snapshots
        new_dups = {}
        old_objs = {}
        for nm in desired_names:
            snap_obj, dest_coll = find_snapshot_obj_and_dest(nm)
            if not snap_obj:
                # If we can't find snapshot source, keep current if exists
                continue
            try:
                dup = snap_obj.copy()
                if getattr(snap_obj, "data", None) is not None:
                    try:
                        dup.data = snap_obj.data.copy()
                    except Exception:
                        pass
            except Exception:
                continue
            try:
                dup.name = f"{nm}_restored"
            except Exception:
                pass
            curr = src_map.get(nm)
            # Link duplicate to same collections as current (if exists), else to source
            if curr:
                old_objs[nm] = curr
            # Link duplicate into the mirrored destination collection
            linked_any = False
            try:
                dest_coll.objects.link(dup)
                linked_any = True
            except Exception:
                linked_any = False
            if not linked_any:
                try:
                    source.objects.link(dup)
                except Exception:
                    pass
            new_dups[nm] = dup

        # Second pass: ensure parents according to commit metadata
        for nm, dup in list(new_dups.items()):
            pnm = (desired_parent.get(nm) or "")
            if not pnm:
                try:
                    dup.parent = None
                except Exception:
                    pass
                continue
            # Prefer parent among new_dups; fall back to existing object if present
            target_parent = new_dups.get(pnm) or src_map.get(pnm)
            if target_parent is not None:
                try:
                    dup.parent = target_parent
                except Exception:
                    pass
            else:
                try:
                    dup.parent = None
                except Exception:
                    pass

        # Third pass: remove or unlink old objects and fill in missing ones
        for nm in desired_names:
            curr = old_objs.get(nm)
            if curr:
                try:
                    for col in list(curr.users_collection):
                        try:
                            col.objects.unlink(curr)
                        except Exception:
                            pass
                    bpy.data.objects.remove(curr, do_unlink=True)
                except Exception:
                    pass

        # Final: rename dups to original names
        for nm, dup in list(new_dups.items()):
            try:
                dup.name = nm
            except Exception:
                pass

        restored = len(new_dups)
        skipped = max(0, len(desired_names) - restored)

        request_redraw()
        msg = f"Restored {restored} object(s) from snapshot"
        if skipped:
            msg += f", skipped {skipped}"
        if removed_extras:
            msg += f", removed {removed_extras} extra"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GITBLEND_OT_checkout_log(bpy.types.Operator):
    bl_idname = "gitblend.checkout_log"
    bl_label = "Checkout Log Entry"
    bl_description = "Restore the working collection to the state up to the selected log entry"
    bl_options = {'INTERNAL'}

    def _iter_objects_recursive(self, coll):
        for o in coll.objects:
            yield o
        for c in coll.children:
            yield from self._iter_objects_recursive(c)

    def _orig_name(self, id_block):
        try:
            v = id_block.get("gitblend_orig_name", None)
            if isinstance(v, str) and v:
                return v
        except Exception:
            pass
        name = getattr(id_block, "name", "") or ""
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

    def _list_branch_snapshots_upto_uid(self, scene, branch, max_uid: str):
        # Mirror logic from validate._list_branch_snapshots but limit to <= max_uid
        dot = None
        for c in scene.collection.children:
            if c.name == ".gitblend":
                dot = c
                break
        if not dot:
            return []
        import re
        uid_re = re.compile(r"_(\d{10,20})(?:-\d+)?$")
        items = []
        for c in dot.children:
            nm = c.name or ""
            if not nm.startswith(branch):
                continue
            m = uid_re.search(nm)
            uid = m.group(1) if m else ""
            if not uid:
                continue
            if uid <= max_uid:
                items.append((uid, c))
        items.sort(key=lambda t: t[0], reverse=True)
        return [c for _, c in items]

    def execute(self, context):
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

        # Load commits and resolve target index from UI log index
        index = load_index()
        b = (index.get("branches", {})).get(branch) or {}
        commits = b.get("commits", []) or []
        if not commits:
            self.report({'INFO'}, f"No commit history for branch '{branch}'.")
            return {'CANCELLED'}
        ui_idx = getattr(props, "changes_log_index", 0) if props else 0
        if ui_idx < 0:
            ui_idx = 0
        if ui_idx >= len(commits):
            ui_idx = len(commits) - 1
        target = commits[ui_idx]
        target_uid = str(target.get("uid", ""))
        if not target_uid:
            self.report({'WARNING'}, "Selected log entry has no UID; cannot checkout.")
            return {'CANCELLED'}

        # Desired object state at that commit
        commit_objs = target.get("objects", []) or []
        desired_names = [o.get("name", "") for o in commit_objs if o.get("name")]
        desired_parent = {o.get("name", ""): o.get("parent", "") for o in commit_objs if o.get("name")}

        source = ensure_source_collection(scene)
        if not source:
            self.report({'WARNING'}, "No top-level collection to restore into.")
            return {'CANCELLED'}

        # Prepare source maps
        src_map = self._build_name_map(source, snapshot=False)

        # Build snapshot search list newest->oldest, but only up to target UID
        snapshots = self._list_branch_snapshots_upto_uid(scene, branch, target_uid)
        snap_maps = [self._build_name_map(s, snapshot=True) for s in snapshots]

        def find_snapshot_obj(nm: str):
            for mp in snap_maps:
                o = mp.get(nm)
                if o is not None:
                    return o
            return None

        # Remove any objects not part of the committed set
        removed_extras = 0
        for nm, obj in list(src_map.items()):
            if nm not in desired_names:
                try:
                    for col in list(obj.users_collection):
                        try:
                            col.objects.unlink(obj)
                        except Exception:
                            pass
                    bpy.data.objects.remove(obj, do_unlink=True)
                    removed_extras += 1
                except Exception:
                    pass

        # Rebuild map after removals
        src_map = self._build_name_map(source, snapshot=False)

        # First pass: create or replace all desired objects from snapshots up to target
        new_dups = {}
        old_objs = {}
        for nm in desired_names:
            snap_obj = find_snapshot_obj(nm)
            if not snap_obj:
                # If we can't find snapshot source, keep current if exists
                continue
            try:
                dup = snap_obj.copy()
                if getattr(snap_obj, "data", None) is not None:
                    try:
                        dup.data = snap_obj.data.copy()
                    except Exception:
                        pass
            except Exception:
                continue
            try:
                dup.name = f"{nm}_restored"
            except Exception:
                pass
            curr = src_map.get(nm)
            colls = []
            if curr:
                old_objs[nm] = curr
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
            new_dups[nm] = dup

        # Second pass: ensure parents according to commit metadata
        for nm, dup in list(new_dups.items()):
            pnm = (desired_parent.get(nm) or "")
            if not pnm:
                try:
                    dup.parent = None
                except Exception:
                    pass
                continue
            target_parent = new_dups.get(pnm) or src_map.get(pnm)
            if target_parent is not None:
                try:
                    dup.parent = target_parent
                except Exception:
                    pass
            else:
                try:
                    dup.parent = None
                except Exception:
                    pass

        # Third pass: remove or unlink old objects and fill in missing ones
        for nm in desired_names:
            curr = old_objs.get(nm)
            if curr:
                try:
                    for col in list(curr.users_collection):
                        try:
                            col.objects.unlink(curr)
                        except Exception:
                            pass
                    bpy.data.objects.remove(curr, do_unlink=True)
                except Exception:
                    pass

        # Final: rename dups to original names
        for nm, dup in list(new_dups.items()):
            try:
                dup.name = nm
            except Exception:
                pass

        restored = len(new_dups)
        skipped = max(0, len(desired_names) - restored)

        request_redraw()
        msg = f"Checked out commit {ui_idx+1}/{len(commits)}"
        m = (target.get("message", "") or "").strip()
        if m:
            msg += f": {m}"
        if skipped:
            msg += f" (skipped {skipped})"
        if removed_extras:
            msg += f", removed {removed_extras} extra"
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
