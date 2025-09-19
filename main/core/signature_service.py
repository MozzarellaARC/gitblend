"""
SignatureService - Handles all data block signature and hash calculations for GitBlend.

This service centralizes all the logic for:
- Generating data signatures for change detection
- Calculating hashes for meshes, materials, node trees, etc.
- Handling modifiers and constraints hashing
- Optimized mesh geometry analysis
"""

import bpy
import hashlib
from typing import Dict, Any, Set, Optional


class SignatureService:
    """Service for calculating data block signatures and hashes."""
    
    @staticmethod
    def generate_data_signature() -> Dict[str, Any]:
        """Generate a comprehensive signature of current data blocks for change detection."""
        signature = {
            "objects": {},
            "meshes": {},
            "materials": {},
            "images": {},
            "texts": {},
            "actions": {},
            "node_groups": {}
        }
        
        # Objects signature
        for obj in bpy.data.objects:
            obj_sig = {
                "name": obj.name,
                "type": obj.type,
                "location": [round(x, 6) for x in obj.location] if hasattr(obj, 'location') else None,
                "rotation": [round(x, 6) for x in obj.rotation_euler] if hasattr(obj, 'rotation_euler') else None,
                "scale": [round(x, 6) for x in obj.scale] if hasattr(obj, 'scale') else None,
                "data_name": obj.data.name if obj.data else None,
                "visible": obj.visible_get() if hasattr(obj, 'visible_get') else True,
                "hide_viewport": obj.hide_viewport if hasattr(obj, 'hide_viewport') else False,
                "modifiers_hash": SignatureService._calculate_modifiers_hash(obj),
                "constraints_hash": SignatureService._calculate_constraints_hash(obj)
            }
            signature["objects"][obj.name] = obj_sig
        
        # Meshes signature
        for mesh in bpy.data.meshes:
            geometry_hash = SignatureService._calculate_mesh_geometry_hash(mesh)
            
            mesh_sig = {
                "name": mesh.name,
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "materials": [mat.name if mat else None for mat in mesh.materials],
                "geometry_hash": geometry_hash
            }
            signature["meshes"][mesh.name] = mesh_sig
        
        # Materials signature
        for mat in bpy.data.materials:
            mat_sig = {
                "name": mat.name,
                "use_nodes": mat.use_nodes,
                "diffuse_color": [round(x, 4) for x in mat.diffuse_color] if hasattr(mat, 'diffuse_color') else None,
                "roughness": round(mat.roughness, 4) if hasattr(mat, 'roughness') else None,
                "metallic": round(mat.metallic, 4) if hasattr(mat, 'metallic') else None,
                "alpha": round(mat.alpha, 4) if hasattr(mat, 'alpha') else None
            }
            
            # Add node tree hash if using nodes
            if mat.use_nodes and mat.node_tree:
                mat_sig["node_tree_hash"] = SignatureService._calculate_node_tree_hash(mat.node_tree)
            
            signature["materials"][mat.name] = mat_sig
        
        # Images signature
        for img in bpy.data.images:
            img_sig = {
                "name": img.name,
                "size": list(img.size) if hasattr(img, 'size') else None,
                "filepath": img.filepath if hasattr(img, 'filepath') else None,
                "file_format": img.file_format if hasattr(img, 'file_format') else None
            }
            signature["images"][img.name] = img_sig
        
        # Texts signature
        for text in bpy.data.texts:
            text_sig = {
                "name": text.name,
                "lines_count": len(text.lines) if hasattr(text, 'lines') else 0,
                "content_hash": hashlib.md5(text.as_string().encode()).hexdigest() if hasattr(text, 'as_string') else None
            }
            signature["texts"][text.name] = text_sig
        
        # Actions signature
        for action in bpy.data.actions:
            action_sig = {
                "name": action.name,
                "frame_range": list(action.frame_range) if hasattr(action, 'frame_range') else None,
                "fcurves_count": len(action.fcurves) if hasattr(action, 'fcurves') else 0
            }
            signature["actions"][action.name] = action_sig
        
        # Node groups signature
        for node_group in bpy.data.node_groups:
            node_group_sig = {
                "name": node_group.name,
                "type": getattr(node_group, 'type', 'UNKNOWN'),
                "nodes_count": len(node_group.nodes) if hasattr(node_group, 'nodes') else 0,
                "links_count": len(node_group.links) if hasattr(node_group, 'links') else 0,
                "content_hash": SignatureService._calculate_simple_node_group_hash(node_group)
            }
            signature["node_groups"][node_group.name] = node_group_sig
        
        return signature
    
    @staticmethod
    def _calculate_mesh_geometry_hash(mesh) -> str:
        """Calculate a hash of mesh geometry to detect vertex-level changes."""
        try:
            vertex_count = len(mesh.vertices)
            
            if vertex_count > 10000:  # Use optimized method for large meshes
                return SignatureService._calculate_optimized_mesh_hash(mesh)
            else:  # Use detailed method for smaller meshes
                return SignatureService._calculate_detailed_mesh_hash(mesh)
                
        except Exception:
            # If we can't calculate geometry hash, use a basic fallback
            try:
                simple_data = f"{len(mesh.vertices)}_{len(mesh.polygons)}_{len(mesh.edges)}"
                return hashlib.md5(simple_data.encode()).hexdigest()
            except Exception:
                return "unknown"
    
    @staticmethod
    def _calculate_detailed_mesh_hash(mesh) -> str:
        """Detailed hash calculation for smaller meshes (< 10K vertices)."""
        mesh.calc_loop_triangles()
        
        # Collect vertex coordinates
        vertex_data = []
        for vertex in mesh.vertices:
            vertex_data.extend([
                round(vertex.co.x, 6),
                round(vertex.co.y, 6),
                round(vertex.co.z, 6),
                round(vertex.normal.x, 6),
                round(vertex.normal.y, 6),
                round(vertex.normal.z, 6)
            ])
        
        # Include face data for topology changes
        face_data = []
        for poly in mesh.polygons:
            face_verts = sorted(poly.vertices)
            face_data.extend(face_verts)
            face_data.extend([
                round(poly.normal.x, 6),
                round(poly.normal.y, 6),
                round(poly.normal.z, 6)
            ])
        
        # Combine all geometry data and create hash
        geometry_data = vertex_data + face_data
        geometry_string = ','.join(map(str, geometry_data))
        
        return hashlib.md5(geometry_string.encode()).hexdigest()
    
    @staticmethod
    def _calculate_optimized_mesh_hash(mesh) -> str:
        """Optimized hash calculation for large meshes (>= 10K vertices)."""
        hash_components = []
        
        # 1. Basic mesh statistics
        hash_components.extend([
            len(mesh.vertices),
            len(mesh.polygons), 
            len(mesh.edges)
        ])
        
        # 2. Bounding box
        if mesh.vertices:
            min_x = min(v.co.x for v in mesh.vertices)
            max_x = max(v.co.x for v in mesh.vertices)
            min_y = min(v.co.y for v in mesh.vertices)
            max_y = max(v.co.y for v in mesh.vertices)
            min_z = min(v.co.z for v in mesh.vertices)
            max_z = max(v.co.z for v in mesh.vertices)
            
            hash_components.extend([
                round(min_x, 4), round(max_x, 4),
                round(min_y, 4), round(max_y, 4),
                round(min_z, 4), round(max_z, 4)
            ])
        
        # 3. Strategic vertex sampling
        vertex_count = len(mesh.vertices)
        sample_size = min(500, vertex_count // 20)
        
        if sample_size > 0:
            step = max(1, vertex_count // sample_size)
            sampled_vertices = mesh.vertices[::step][:sample_size]
            
            for vertex in sampled_vertices:
                hash_components.extend([
                    round(vertex.co.x, 4),
                    round(vertex.co.y, 4),
                    round(vertex.co.z, 4)
                ])
        
        # 4. Surface area approximation
        try:
            mesh.calc_loop_triangles()
            total_area = sum(tri.area for tri in mesh.loop_triangles[:100])
            hash_components.append(round(total_area, 4))
        except:
            pass
        
        # 5. Create hash from components
        hash_string = ','.join(map(str, hash_components))
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    @staticmethod
    def _calculate_node_tree_hash(node_tree) -> str:
        """Calculate a hash of material node tree to detect node changes."""
        try:
            node_data = []
            
            # Collect node information
            for node in node_tree.nodes:
                node_info = [
                    node.name,
                    node.type,
                    str(node.location.x),
                    str(node.location.y)
                ]
                
                # Add input values for nodes with default values
                for input_socket in node.inputs:
                    if hasattr(input_socket, 'default_value'):
                        try:
                            if hasattr(input_socket.default_value, '__iter__'):
                                # Vector/Color values
                                node_info.extend([str(round(x, 4)) for x in input_socket.default_value])
                            else:
                                # Scalar values
                                node_info.append(str(round(input_socket.default_value, 4)))
                        except (TypeError, AttributeError):
                            pass
                
                node_data.extend(node_info)
            
            # Collect link information
            for link in node_tree.links:
                link_info = [
                    link.from_node.name,
                    link.from_socket.name,
                    link.to_node.name,
                    link.to_socket.name
                ]
                node_data.extend(link_info)
            
            # Create hash from all node data
            node_string = ','.join(node_data)
            return hashlib.md5(node_string.encode()).hexdigest()
            
        except Exception:
            # Fallback: basic node count
            try:
                basic_data = f"{len(node_tree.nodes)}_{len(node_tree.links)}"
                return hashlib.md5(basic_data.encode()).hexdigest()
            except Exception:
                return "unknown"
    
    @staticmethod
    def _calculate_simple_node_group_hash(node_group) -> str:
        """Calculate a simplified hash for node group change detection."""
        try:
            # Use node count and basic node type counts for change detection
            node_type_counts = {}
            for node in node_group.nodes:
                node_type = getattr(node, 'type', 'UNKNOWN')
                node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
            
            # Create a simple hash from counts
            hash_data = [
                len(node_group.nodes),
                len(node_group.links),
                str(sorted(node_type_counts.items()))
            ]
            
            hash_string = '_'.join(map(str, hash_data))
            return hashlib.md5(hash_string.encode()).hexdigest()
            
        except Exception:
            # Fallback to basic counting if detailed analysis fails
            try:
                basic_data = f"{len(node_group.nodes)}_{len(node_group.links)}"
                return hashlib.md5(basic_data.encode()).hexdigest()
            except Exception:
                return "unknown"
    
    @staticmethod
    def _calculate_modifiers_hash(obj) -> str:
        """Calculate a hash of object modifiers using recursive property introspection."""
        try:
            if not hasattr(obj, 'modifiers') or not obj.modifiers:
                return "no_modifiers"
            
            modifier_data = []
            
            for mod in obj.modifiers:
                # Get all modifier properties recursively
                mod_props = SignatureService._get_object_properties_recursive(mod, visited=set())
                modifier_data.append(mod_props)
            
            # Create hash from all modifier data
            modifier_string = str(sorted(modifier_data))
            return hashlib.md5(modifier_string.encode()).hexdigest()
            
        except Exception:
            # Fallback: basic modifier count and types
            try:
                basic_data = f"{len(obj.modifiers)}_{'_'.join([m.type for m in obj.modifiers])}"
                return hashlib.md5(basic_data.encode()).hexdigest()
            except Exception:
                return "unknown_modifiers"
    
    @staticmethod
    def _calculate_constraints_hash(obj) -> str:
        """Calculate a hash of object constraints using recursive property introspection."""
        try:
            if not hasattr(obj, 'constraints') or not obj.constraints:
                return "no_constraints"
            
            constraint_data = []
            
            for constraint in obj.constraints:
                # Get all constraint properties recursively
                constraint_props = SignatureService._get_object_properties_recursive(constraint, visited=set())
                constraint_data.append(constraint_props)
            
            # Create hash from all constraint data
            constraint_string = str(sorted(constraint_data))
            return hashlib.md5(constraint_string.encode()).hexdigest()
            
        except Exception:
            # Fallback: basic constraint count and types
            try:
                basic_data = f"{len(obj.constraints)}_{'_'.join([c.type for c in obj.constraints])}"
                return hashlib.md5(basic_data.encode()).hexdigest()
            except Exception:
                return "unknown_constraints"
    
    @staticmethod
    def _get_object_properties_recursive(obj, visited=None, max_depth=3, current_depth=0):
        """Recursively extract properties from any Blender object for change detection."""
        if visited is None:
            visited = set()
        
        # Prevent infinite recursion
        if current_depth >= max_depth or id(obj) in visited:
            return str(type(obj).__name__)
        
        visited.add(id(obj))
        
        try:
            # Handle basic types
            if obj is None:
                return "None"
            
            if isinstance(obj, (str, int, float, bool)):
                return str(obj)
            
            if isinstance(obj, (list, tuple)):
                if len(obj) > 10:  # Limit very large collections
                    return f"{type(obj).__name__}[{len(obj)}]"
                return [SignatureService._get_object_properties_recursive(item, visited, max_depth, current_depth + 1) for item in obj]
            
            # Handle Vector/Euler/Color types (common in Blender)
            if hasattr(obj, '__len__') and hasattr(obj, '__getitem__'):
                try:
                    if len(obj) <= 4:  # Typical for Vector3, Vector4, Euler, Color
                        return [round(float(obj[i]), 6) for i in range(len(obj))]
                except (TypeError, ValueError):
                    pass
            
            # For Blender objects, extract relevant properties
            if hasattr(obj, 'bl_rna'):
                properties = {}
                
                # Get all properties from bl_rna
                for prop in obj.bl_rna.properties:
                    if prop.identifier.startswith('_'):
                        continue  # Skip private properties
                    
                    try:
                        value = getattr(obj, prop.identifier)
                        
                        # Skip functions and complex objects that might cause issues
                        if callable(value):
                            continue
                        
                        # Handle special Blender object references
                        if hasattr(value, 'name') and hasattr(value, 'bl_rna'):
                            properties[prop.identifier] = f"{type(value).__name__}:{value.name}"
                        else:
                            properties[prop.identifier] = SignatureService._get_object_properties_recursive(
                                value, visited, max_depth, current_depth + 1
                            )
                    except (AttributeError, RuntimeError, TypeError):
                        # Some properties might not be accessible
                        continue
                
                return properties
            
            # Fallback: try to get basic attributes
            if hasattr(obj, '__dict__'):
                return str(sorted(obj.__dict__.items()))
            
            return str(obj)
            
        except Exception:
            return f"{type(obj).__name__}_error"
        finally:
            visited.discard(id(obj))