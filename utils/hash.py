import bpy
import hashlib

SHA256 = hashlib.sha256

def bpy_data_serde():
    for obj in bpy.data.objects:
            obj_ptrs = obj.data
            print(f"{obj.name} -> {obj_ptrs.name}")
            
            # Get all modifiers and their children attributes
            print("Modifiers:")
            for mod in obj.modifiers:
                print(f"-> {mod.name}")
                for attr in dir(mod):
                    if not attr.startswith("_"):
                        value = getattr(mod, attr)
                        if isinstance(value, (str, int, float, bool)):
                            print(f"   - {attr}: {value}")
            
def get_object_data():
    for obj in bpy.data.objects:
        print(obj.name)

def get_mesh_data():
    for mesh in bpy.data.meshes:
        print(mesh.name)