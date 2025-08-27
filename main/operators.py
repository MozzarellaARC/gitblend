import bpy
from datetime import datetime
from .validate import (
    ensure_gitblend_collection,
    slugify,
    duplicate_collection_hierarchy,
    remap_parenting,
)
from .draw import _gitblend_request_redraw


class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Copy current top-level collections (except .gitblend) into .gitblend with unique names and add an entry to the change log"
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

        # Unique id for this commit: message slug + selected enum (if any); fallback to timestamp
        uid_parts = []
        # First, selected enum (acts as a prefix)
        idx = getattr(props, "string_items_index", -1)
        if 0 <= idx < len(props.string_items):
            sel = (props.string_items[idx].name or "").strip()
            sel_slug = slugify(sel)
            if sel_slug:
                uid_parts.append(sel_slug)
        # Then, the commit message slug
        msg_slug = slugify(msg)
        if msg_slug:
            uid_parts.append(msg_slug)
        uid = "-".join(uid_parts) if uid_parts else ""
        if not uid:
            uid = datetime.now().strftime("%Y%m%d%H%M%S")

        # Keep a map of original->duplicate to later remap parenting
        obj_map: dict[bpy.types.Object, bpy.types.Object] = {}

        # Copy all top-level collections except .gitblend
        copied_any = False
        for top in list(root.children):
            if top.name == ".gitblend":
                continue
            duplicate_collection_hierarchy(top, dot_coll, uid, obj_map)
            copied_any = True

        # Remap parenting to use duplicated parents when available
        remap_parenting(obj_map)

        # Log commit entry
        item = props.changes_log.add()
        item.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item.message = msg
        props.commit_message = ""

        # Redraw UI
        _gitblend_request_redraw()

        if copied_any:
            self.report({'INFO'}, "Commit snapshot created in .gitblend")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No top-level collections to copy")
            return {'CANCELLED'}


class GITBLEND_OT_initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Create .gitblend collection, optionally rename existing top collection to preferred name, and copy it into .gitblend"
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

        # Rename existing collection to preferred name if needed and available
        if existing.name != root_branch:
            # Only rename if the preferred name is free, otherwise keep existing name
            if bpy.data.collections.get(root_branch) is None:
                existing.name = root_branch

        # Unique id for initialization copies: use constant 'init'
        uid = "init"

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
