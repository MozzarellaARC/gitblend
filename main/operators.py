import bpy


class YANT_OT_clear_save_log(bpy.types.Operator):
    bl_idname = "yant.clear_save_log"
    bl_label = "Clear YANT Save Log"
    bl_description = "Clear the recorded save events"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        props = getattr(context.scene, "yant_props", None)
        if props:
            props.save_events.clear()
        self.report({'INFO'}, "YANT save log cleared")
        return {'FINISHED'}


class YANT_OT_add_dummy_event(bpy.types.Operator):
    bl_idname = "yant.add_dummy_event"
    bl_label = "Add Test Save Entry"
    bl_description = "Add a dummy save event to test the panel UI"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from datetime import datetime
        props = getattr(context.scene, "yant_props", None)
        if not props:
            self.report({'WARNING'}, "YANT properties missing")
            return {'CANCELLED'}
        item = props.save_events.add()
        item.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item.filepath = bpy.data.filepath or "(unsaved file)"
        self.report({'INFO'}, "Dummy save event added")
        return {'FINISHED'}


def register_operators():
    bpy.utils.register_class(YANT_OT_clear_save_log)
    bpy.utils.register_class(YANT_OT_add_dummy_event)


def unregister_operators():
    bpy.utils.unregister_class(YANT_OT_add_dummy_event)
    bpy.utils.unregister_class(YANT_OT_clear_save_log)
