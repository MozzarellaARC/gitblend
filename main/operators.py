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

        # Unique id for this commit: use commit message slug; fallback to timestamp if empty
        uid = slugify(msg)
        if not uid:
            # If slug is empty due to symbols-only message, fallback to timestamp
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
    bl_description = "Create .gitblend collection, rename existing top collection to 'main', and copy it into .gitblend"
    bl_options = {'INTERNAL'}  # exclude from undo/redo and search

    def execute(self, context):
        # Access addon properties for logging
        props = getattr(context.scene, "gitblend_props", None)

        scene = context.scene
        root = scene.collection

        # If .gitblend already exists, abort with an error but keep the button enabled
        for c in root.children:
            if c.name == ".gitblend":
                self.report({'ERROR'}, "'.gitblend' collection already exists; initialization aborted.")
                return {'CANCELLED'}

        # Prefer a top-level collection named 'main' if present; otherwise first non-.gitblend
        existing = None
        for c in list(root.children):
            if c.name == "main":
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

        # Rename existing collection to 'main' if needed
        if existing.name != "main":
            # Only rename to 'main' if the name is free, otherwise keep existing name
            if bpy.data.collections.get("main") is None:
                existing.name = "main"

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

        self.report({'INFO'}, "Initialized .gitblend and copied 'main' collection")
        return {'FINISHED'}

def register_operators():
    bpy.utils.register_class(GITBLEND_OT_commit)
    bpy.utils.register_class(GITBLEND_OT_initialize)


def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_initialize)
    bpy.utils.unregister_class(GITBLEND_OT_commit)
