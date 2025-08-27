import bpy


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

    def execute(self, context):
        scene = context.scene
        root = scene.collection  # "Scene Collection"

        # Ensure a top-level collection exists (other than .gitblend)
        existing = None
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

        # Rename existing collection to 'main' if needed
        if existing.name != "main":
            existing.name = "main"

        # Copy the collection hierarchy into .gitblend (linking same objects, not duplicating)
        def copy_collection(src: bpy.types.Collection, parent: bpy.types.Collection):
            new_coll = bpy.data.collections.new(src.name)
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
