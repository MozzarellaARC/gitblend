import bpy
from datetime import datetime
from .validate import (
    ensure_gitblend_collection,
    duplicate_collection_hierarchy,
    remap_parenting,
)
from .draw import _gitblend_request_redraw


class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Rename the source collection to the selected prefix and copy it into .gitblend with a UID suffix; log the message"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        props = getattr(context.scene, "gitblend_props", None)
        if not props:
            self.report({'ERROR'}, "GITBLEND properties not found")
            return {'CANCELLED'}

        msg = (props.commit_message or "").strip()
        # Require a non-empty commit message but keep button enabled; show error and cancel
        if not msg:
            self.report({'ERROR'}, "Please enter a commit message before committing.")
            return {'CANCELLED'}

        scene = context.scene
        root = scene.collection
        dot_coll = ensure_gitblend_collection(scene)

        # Determine desired prefix from selected enum (fallback to stored branch or 'main')
        sel = ""
        idx = getattr(props, "string_items_index", -1)
        if 0 <= idx < len(props.string_items):
            sel = (props.string_items[idx].name or "").strip()
        if not sel:
            sel = (getattr(props, "gitblend_branch", "") or "").strip() or "main"

        # Choose source collection: prefer one named exactly as prefix; otherwise first non-.gitblend
        source = None
        for c in list(root.children):
            if c.name == sel:
                source = c
                break
        if not source:
            for c in list(root.children):
                if c.name != ".gitblend":
                    source = c
                    break

        if not source:
            self.report({'WARNING'}, "No top-level collection to commit")
            return {'CANCELLED'}

        # Rename source to match prefix (if not already)
        if source.name != sel:
            # Extra safety: if another collection already has this name, use that as source instead of renaming
            other = bpy.data.collections.get(sel)
            if other and other is not source:
                source = other
            else:
                try:
                    source.name = sel
                except Exception:
                    pass

        # Unique id for this commit (timestamp only for .gitblend duplicate name)
        uid = datetime.now().strftime("%Y%m%d%H%M%S")

        # Duplicate only the source into .gitblend, with names suffixed by UID
        obj_map: dict[bpy.types.Object, bpy.types.Object] = {}
        duplicate_collection_hierarchy(source, dot_coll, uid, obj_map)

        # Remap parenting to use duplicated parents when available
        remap_parenting(obj_map)

        # Log commit entry
        item = props.changes_log.add()
        item.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item.message = msg
        props.commit_message = ""

        # Redraw UI
        _gitblend_request_redraw()

        self.report({'INFO'}, "Commit snapshot created in .gitblend")
        return {'FINISHED'}


class GITBLEND_OT_initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Create .gitblend; rename source to preferred root name; copy it into .gitblend with a UID suffix"
    bl_options = {'INTERNAL'}  # exclude from undo/redo and search

    def execute(self, context):
        # Access addon properties for logging and preferred root name
        props = getattr(context.scene, "gitblend_props", None)
        root_branch = None
        if props:
            # Ensure enum contains 'init'
            try:
                has_init = any((it.name or "").strip() == "init" for it in props.string_items)
            except Exception:
                has_init = True
            if not has_init:
                try:
                    it = props.string_items.add()
                    it.name = "init"
                except Exception:
                    pass

            # Use the first element of the enum as root branch if available
            if len(props.string_items) > 0:
                nm = (props.string_items[0].name or "").strip()
                if nm:
                    root_branch = nm
            # Fallback to stored branch name
            if not root_branch:
                root_branch = (props.gitblend_branch or "").strip()
        if not root_branch:
            root_branch = "main"

        scene = context.scene
        root = scene.collection

        # If .gitblend already exists, abort with an error but keep the button enabled
        for c in root.children:
            if c.name == ".gitblend":
                self.report({'ERROR'}, "'.gitblend' collection already exists; initialization aborted.")
                return {'CANCELLED'}

        # Prefer a top-level collection named per preference if present; otherwise first non-.gitblend
        existing = None
        for c in list(root.children):
            if c.name == root_branch:
                existing = c
                break
        if not existing:
            for c in list(root.children):
                if c.name != ".gitblend":
                    existing = c
                    break

        if not existing:
            self.report({'WARNING'}, "No top-level collection to initialize")
            return {'CANCELLED'}

        # Create .gitblend and exclude it in all view layers
        dot_coll = ensure_gitblend_collection(scene)

        # Rename the original collection to the preferred root name so source matches prefix
        if existing.name != root_branch:
            # If another collection already has the desired name, switch to it to avoid duplicates
            same = bpy.data.collections.get(root_branch)
            if same and same is not existing:
                existing = same
            else:
                try:
                    existing.name = root_branch
                except Exception:
                    pass

        # Unique id for initialization copies: use timestamp
        uid = datetime.now().strftime("%Y%m%d%H%M%S")

        # Keep a map of original->duplicate to later remap parenting
        obj_map: dict[bpy.types.Object, bpy.types.Object] = {}
        duplicate_collection_hierarchy(existing, dot_coll, uid, obj_map)

        # Remap parenting to use duplicated parents when available
        remap_parenting(obj_map)

        # Log initialize entry so it shows in the panel change log
        try:
            if props:
                item = props.changes_log.add()
                item.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                item.message = f"Initialize: copied '{existing.name}' into .gitblend"
        except Exception:
            # Non-fatal if logging fails
            pass

        # Request UI redraw so the panel updates immediately
        _gitblend_request_redraw()

        self.report({'INFO'}, f"Initialized .gitblend and copied '{existing.name}' collection")
        return {'FINISHED'}


class GITBLEND_OT_string_add(bpy.types.Operator):
    bl_idname = "gitblend.string_add"
    bl_label = "Add String Item"
    bl_description = "Add a new item to the string list"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        props = getattr(context.scene, "gitblend_props", None)
        if not props:
            self.report({'ERROR'}, "GITBLEND properties not found")
            return {'CANCELLED'}
        item = props.string_items.add()
        item.name = ""
        props.string_items_index = len(props.string_items) - 1
        props.selected_string = str(props.string_items_index)
        _gitblend_request_redraw()
        return {'FINISHED'}


class GITBLEND_OT_string_remove(bpy.types.Operator):
    bl_idname = "gitblend.string_remove"
    bl_label = "Remove String Item"
    bl_description = "Remove the selected item from the string list"
    bl_options = {'INTERNAL'}
    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        props = getattr(context.scene, "gitblend_props", None)
        if not props:
            self.report({'ERROR'}, "GITBLEND properties not found")
            return {'CANCELLED'}
        idx = self.index if self.index >= 0 else props.string_items_index
        if 0 <= idx < len(props.string_items):
            props.string_items.remove(idx)
            # Adjust index
            props.string_items_index = max(0, min(idx, len(props.string_items) - 1))
            # Update dropdown selection
            if len(props.string_items) > 0:
                props.selected_string = str(props.string_items_index)
            else:
                props.selected_string = "-1"
            _gitblend_request_redraw()
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
