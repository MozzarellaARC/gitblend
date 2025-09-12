import bpy

class GITBLEND_Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    # Define your preferences properties here
    my_property: bpy.props.StringProperty(name="My Property", default="Default Value")

    def draw(self, context):
        layout = self.layout
        layout.label(text="GITBLEND Preferences")
        layout.prop(self, "my_property")
