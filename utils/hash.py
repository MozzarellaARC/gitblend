import bpy
import hashlib

SHA256 = hashlib.sha256

def bpy_data_serde():
    for obj in bpy.data.objects:
            obj_ptrs = obj.data
            print(f"{obj.name} -> {obj_ptrs.name}")
            # Get all modifiers
            print("Modifiers:")
            for mod in obj.modifiers:
                print(f"-> {mod.name}")
            
            print("Particles:")
            for p in obj.particle_systems:
                print(f"-> {p.name}")

            # Physics are not itterable, so we check if they exist

            print("Constraints:")
            for con in obj.constraints:
                print(f"-> {con.name}")

            print("Data:")
            if obj_ptrs is not None:
                print(f"-> {obj_ptrs.name} ({obj_ptrs.__class__.__name__})")
                if obj_ptrs.__class__.__name__ == "Mesh":
                    mesh = obj_ptrs
                    print("  Vertices:")
                    for v in mesh.vertices:
                        print(f"  -> {v.index}: {v.co}")
                    print("  Edges:")
                    for e in mesh.edges:
                        print(f"  -> {e.index}: {e.vertices[:]}")
                    print("  Faces:")
                    for f in mesh.polygons:
                        print(f"  -> {f.index}: {f.vertices[:]}")
            else:
                print("-> No data")

            print("Materials:")
            for mat in obj.data.materials:
                print(f"-> {mat.name}")

def get_object_data():
    for obj in bpy.data.objects:
        print(obj.name)

def get_mesh_data():
    for mesh in bpy.data.meshes:
        print(mesh.name)