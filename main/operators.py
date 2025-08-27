import bpy
from .validate import (
    ensure_gitblend_collection,
    slugify,
    duplicate_collection_hierarchy,
    remap_parenting,
    get_latest_snapshot,
    create_diff_snapshot_with_changes,
)
from .utils import (
    now_str,
    request_redraw,
    get_props,
    get_selected_branch,
    find_preferred_or_first_non_dot,
    log_change,
    ensure_enum_contains,
    set_dropdown_selection,
)
from .index import (
    load_index,
    save_index,
    compute_collection_signature,
    get_latest_commit,
    derive_changed_set,
    update_index_with_commit,
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
        # Require existing .gitblend collection for commit
        has_gitblend = any(c.name == ".gitblend" for c in scene.collection.children)
        if not has_gitblend:
            self.report({'ERROR'}, "'.gitblend' collection does not exist. Click Initialize first.")
            return {'CANCELLED'}

        sel = get_selected_branch(props)
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

        dot_coll = ensure_gitblend_collection(scene)

        # Compute signatures and compare with TOML index for early decision
        obj_sigs, coll_hash = compute_collection_signature(source)
        index = load_index()
        last = get_latest_commit(index, sel)
        prev_objs = {}
        if last:
            prev_objs = {o.get("name", ""): o for o in last.get("objects", []) if (o.get("name", ""))}
        has_changes, changed_names = derive_changed_set(obj_sigs, prev_objs)
        if not has_changes:
            self.report({'INFO'}, "No changes detected; skipping snapshot")
            return {'CANCELLED'}

        uid = now_str("%Y%m%d%H%M%S")

        prev = get_latest_snapshot(scene, sel)
        # Differential snapshot: provide changed names from TOML to avoid recomputing and ensure parity
        changed_set = set(changed_names)
        new_coll, obj_map = create_diff_snapshot_with_changes(source, dot_coll, uid, prev, changed_set)
        # remap_parenting only needed for newly copied objects; handled inside create_diff_snapshot

        # Update TOML index
        snapshot_name = new_coll.name
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
        props = get_props(context)
        root_branch = None
        if props:
            ensure_enum_contains(props, "main")
            if len(props.string_items) > 0:
                nm = (props.string_items[0].name or "").strip()
                if nm:
                    root_branch = nm
            if not root_branch:
                root_branch = (props.gitblend_branch or "").strip()
        if not root_branch:
            root_branch = "main"

        scene = context.scene
        for c in scene.collection.children:
            if c.name == ".gitblend":
                self.report({'ERROR'}, "'.gitblend' collection already exists; initialization aborted.")
                return {'CANCELLED'}

        existing = find_preferred_or_first_non_dot(scene, root_branch)
        if not existing:
            self.report({'WARNING'}, "No top-level collection to initialize")
            return {'CANCELLED'}

        dot_coll = ensure_gitblend_collection(scene)

        if existing.name != root_branch:
            same = bpy.data.collections.get(root_branch)
            if same and same is not existing:
                existing = same
            else:
                try:
                    existing.name = root_branch
                except Exception:
                    pass

        uid = now_str("%Y%m%d%H%M%S")

        obj_map: dict[bpy.types.Object, bpy.types.Object] = {}
        duplicate_collection_hierarchy(existing, dot_coll, uid, obj_map)
        remap_parenting(obj_map)

        if props:
            log_change(props, f"Initialize: copied '{existing.name}' into .gitblend")

        request_redraw()

        self.report({'INFO'}, f"Initialized .gitblend and copied '{existing.name}' collection")
        return {'FINISHED'}


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

def register_operators():
    bpy.utils.register_class(GITBLEND_OT_commit)
    bpy.utils.register_class(GITBLEND_OT_initialize)
    bpy.utils.register_class(GITBLEND_OT_string_add)
    bpy.utils.register_class(GITBLEND_OT_string_remove)


def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_string_remove)
    bpy.utils.unregister_class(GITBLEND_OT_string_add)
    bpy.utils.unregister_class(GITBLEND_OT_initialize)
    bpy.utils.unregister_class(GITBLEND_OT_commit)
