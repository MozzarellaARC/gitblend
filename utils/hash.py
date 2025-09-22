import bpy
import hashlib

SHA256 = hashlib.sha256

def get_object_data():
    for obj in bpy.data.objects:
        print(obj.name)

def get_mesh_data():
    for mesh in bpy.data.meshes:
        print(mesh.name)