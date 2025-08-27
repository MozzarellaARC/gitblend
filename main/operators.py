import bpy
from datetime import datetime
import uuid


class GITBLEND_OT_clear_save_log(bpy.types.Operator):
    bl_idname = "gitblend.clear_save_log"
    bl_label = "Clear GITBLEND Save Log"
    bl_description = "Clear the recorded save events"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        props = getattr(context.scene, "gitblend_props", None)
        if props:
            props.save_events.clear()
        self.report({'INFO'}, "GITBLEND save log cleared")
        return {'FINISHED'}


class GITBLEND_OT_initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Create .gitblend collection, rename existing top collection to 'main', and copy it into .gitblend"
    bl_options = {'INTERNAL'}  # exclude from undo/redo and search

    def execute(self, context):
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

        self.report({'INFO'}, "Initialized .gitblend and copied 'main' collection")
        return {'FINISHED'}

class GITBLEND_OT_add_dummy_event(bpy.types.Operator):
    bl_idname = "gitblend.add_dummy_event"
    bl_label = "Add Test Save Entry"
    bl_description = "Add a dummy save event to test the panel UI"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from datetime import datetime
        props = getattr(context.scene, "gitblend_props", None)
        if not props:
            self.report({'WARNING'}, "GITBLEND properties missing")
            return {'CANCELLED'}
        item = props.save_events.add()
        item.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item.filepath = bpy.data.filepath or "(unsaved file)"
        self.report({'INFO'}, "Dummy save event added")
        return {'FINISHED'}


def register_operators():
    bpy.utils.register_class(GITBLEND_OT_clear_save_log)
    bpy.utils.register_class(GITBLEND_OT_add_dummy_event)
    bpy.utils.register_class(GITBLEND_OT_initialize)


def unregister_operators():
    bpy.utils.unregister_class(GITBLEND_OT_initialize)
    bpy.utils.unregister_class(GITBLEND_OT_add_dummy_event)
    bpy.utils.unregister_class(GITBLEND_OT_clear_save_log)
