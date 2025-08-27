import bpy
from datetime import datetime
import uuid


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
        # Allow empty message but warn; proceed with copy regardless
        if not msg:
            self.report({'INFO'}, "Commit message empty; proceeding with snapshot copy")

        scene = context.scene
        root = scene.collection  # Scene Collection

        # Ensure .gitblend collection exists under root
        dot_coll = None
        for c in root.children:
            if c.name == ".gitblend":
                dot_coll = c
                break
        if not dot_coll:
            dot_coll = bpy.data.collections.new(".gitblend")
            root.children.link(dot_coll)

        # Exclude .gitblend from all view layers by default
        def find_layer_collection(layer_coll, target_coll):
            if layer_coll.collection == target_coll:
                return layer_coll
            for child in layer_coll.children:
                found = find_layer_collection(child, target_coll)
                if found:
                    return found
            return None

        for vl in scene.view_layers:
            lc = find_layer_collection(vl.layer_collection, dot_coll)
            if lc:
                lc.exclude = True

        # Unique id for this commit to avoid .001 suffixes and group copies
        uid = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]

        def unique_coll_name(base: str) -> str:
            candidate = f"{base}_{uid}"
            if bpy.data.collections.get(candidate) is None:
                return candidate
            i = 1
            while bpy.data.collections.get(f"{candidate}-{i}") is not None:
                i += 1
            return f"{candidate}-{i}"

        # Copy the collection hierarchy (linking same objects)
        def copy_collection(src: bpy.types.Collection, parent: bpy.types.Collection):
            new_name = unique_coll_name(src.name)
            new_coll = bpy.data.collections.new(new_name)
            parent.children.link(new_coll)
            # Link objects
            for obj in src.objects:
                try:
                    new_coll.objects.link(obj)
                except RuntimeError:
                    pass
            # Recurse for child collections
            for child in src.children:
                copy_collection(child, new_coll)
            return new_coll

        # Copy all top-level collections except .gitblend
        copied_any = False
        for top in list(root.children):
            if top.name == ".gitblend":
                continue
            copy_collection(top, dot_coll)
            copied_any = True

        # Log commit entry
        item = props.changes_log.add()
        item.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item.message = msg if msg else f"Snapshot {uid}"
        props.commit_message = ""

        # Redraw UI
        try:
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        except Exception:
            pass

        if copied_any:
            self.report({'INFO'}, "Commit snapshot created in .gitblend")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No top-level collections to copy")
            return {'CANCELLED'}


class GITBLEND_OT_clear_change_log(bpy.types.Operator):
    bl_idname = "gitblend.clear_change_log"
    bl_label = "Clear Change Log"
    bl_description = "Clear all entries in the change log"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        props = getattr(context.scene, "gitblend_props", None)
        if props:
            props.changes_log.clear()
        self.report({'INFO'}, "GITBLEND change log cleared")
        return {'FINISHED'}

class GITBLEND_OT_initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Create .gitblend collection, rename existing top collection to 'main', and copy it into .gitblend"
    bl_options = {'INTERNAL'}  # exclude from undo/redo and search

    def execute(self, context):
        # Access addon properties for logging
        props = getattr(context.scene, "gitblend_props", None)

        scene = context.scene
        root = scene.collection  # "Scene Collection"

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

        # Ensure .gitblend collection exists under root
        dot_coll = None
        for c in root.children:
            if c.name == ".gitblend":
                dot_coll = c
                break
        if not dot_coll:
            dot_coll = bpy.data.collections.new(".gitblend")
            root.children.link(dot_coll)

        # Exclude .gitblend from all view layers by default
        def find_layer_collection(layer_coll, target_coll):
            if layer_coll.collection == target_coll:
                return layer_coll
            for child in layer_coll.children:
                found = find_layer_collection(child, target_coll)
                if found:
                    return found
            return None

        for vl in scene.view_layers:
            lc = find_layer_collection(vl.layer_collection, dot_coll)
            if lc:
                lc.exclude = True

        # Rename existing collection to 'main' if needed
        if existing.name != "main":
            # Only rename to 'main' if the name is free, otherwise keep existing name
            if bpy.data.collections.get("main") is None:
                existing.name = "main"

        # Unique id for this copy operation to avoid .001 suffixes
        uid = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]

        def unique_coll_name(base: str) -> str:
            candidate = f"{base}_{uid}"
            if bpy.data.collections.get(candidate) is None:
                return candidate
            # Extremely unlikely due to uid, but fall back to numbered suffix
            i = 1
            while bpy.data.collections.get(f"{candidate}-{i}") is not None:
                i += 1
            return f"{candidate}-{i}"

        # Copy the collection hierarchy into .gitblend (linking same objects, not duplicating)
        def copy_collection(src: bpy.types.Collection, parent: bpy.types.Collection):
            new_name = unique_coll_name(src.name)
            new_coll = bpy.data.collections.new(new_name)
            parent.children.link(new_coll)
            # Link objects
            for obj in src.objects:
                try:
                    new_coll.objects.link(obj)
                except RuntimeError:
                    # Object may already be linked to this collection
                    pass
            # Recurse for child collections
            for child in src.children:
                copy_collection(child, new_coll)
            return new_coll

        copy_collection(existing, dot_coll)

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
        try:
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        except Exception:
            pass

        self.report({'INFO'}, "Initialized .gitblend and copied 'main' collection")
        return {'FINISHED'}

def register_operators():
    bpy.utils.register_class(GITBLEND_OT_commit)
    bpy.utils.register_class(GITBLEND_OT_initialize)


def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_initialize)
    bpy.utils.unregister_class(GITBLEND_OT_commit)
