import bpy

class YANT_OP(bpy.types.Operators):
    pass

def register_operators():
    bpy.utils.register_class(YANT_OP)

def unregister_operators():
    bpy.utils.unregister_class(YANT_OP)
