import bpy

class YANT_Properties(bpy.types.PropertyGroup):
    pass

def register_properties():
    bpy.utils.register_class(YANT_Properties)
    bpy.types.Scene.yant_props = bpy.props.PointerProperty(type=YANT_Properties)

def unregister_properties():
    bpy.utils.unregister_class(YANT_Properties)
    del bpy.types.Scene.yant_props