"""Diffing functionality for git_blend."""
import bpy
from typing import Dict, List, Any, Tuple
from .utils import (
    get_data_block_info,
    sample_mesh_vertices,
    load_commit_metadata,
    get_gitblend_dir
)


def compare_objects(current_objects: List, stored_objects: List) -> Tuple[List, List, List]:
    """Compare current objects with stored objects.
    Returns: (added, modified, removed)
    """
    stored_dict = {obj["name"]: obj for obj in stored_objects}
    current_dict = {obj.name: obj for obj in current_objects}
    
    added = []
    modified = []
    removed = []
    
    # Find added and modified objects
    for name, obj in current_dict.items():
        if name not in stored_dict:
            added.append(obj)
        else:
            stored_obj = stored_dict[name]
            current_info = get_data_block_info(obj)
            
            # For objects, we should not compare vertex count here as that's handled in mesh comparison
            # Objects should only be compared for basic properties like type
            type_changed = current_info.get("type") != stored_obj.get("type")
            
            # Simple comparison based on type only (mesh changes are handled separately)
            if type_changed:
                modified.append(obj)
    
    # Find removed objects
    for name in stored_dict:
        if name not in current_dict:
            removed.append(stored_dict[name])
    
    return added, modified, removed


def compare_meshes(current_meshes: List, stored_meshes: List) -> Tuple[List, List, List]:
    """Compare current meshes with stored meshes.
    Returns: (added, modified, removed)
    """
    stored_dict = {mesh["name"]: mesh for mesh in stored_meshes}
    current_dict = {mesh.name: mesh for mesh in current_meshes}
    
    added = []
    modified = []
    removed = []
    
    # Find added and modified meshes
    for name, mesh in current_dict.items():
        if name not in stored_dict:
            added.append(mesh)
        else:
            stored_mesh = stored_dict[name]
            
            # Sample vertices for comparison
            current_vertices = sample_mesh_vertices(mesh)
            stored_vertices = stored_mesh.get("vertices_sample", [])
            
            # Convert stored vertices to tuples for consistent comparison
            stored_vertices_tuples = [tuple(v) if isinstance(v, list) else v for v in stored_vertices]
            
            # Compare vertex count and sample
            if (len(mesh.vertices) != stored_mesh.get("vertex_count", 0) or
                len(mesh.polygons) != stored_mesh.get("face_count", 0) or
                current_vertices != stored_vertices_tuples):
                modified.append(mesh)
    
    # Find removed meshes
    for name in stored_dict:
        if name not in current_dict:
            removed.append(stored_dict[name])
    
    return added, modified, removed


def compare_materials(current_materials: List, stored_materials: List) -> Tuple[List, List, List]:
    """Compare current materials with stored materials.
    Returns: (added, modified, removed)
    """
    stored_dict = {mat["name"]: mat for mat in stored_materials}
    current_dict = {mat.name: mat for mat in current_materials}
    
    added = []
    modified = []
    removed = []
    
    # Find added and modified materials
    for name, material in current_dict.items():
        if name not in stored_dict:
            added.append(material)
        else:
            stored_material = stored_dict[name]
            current_node_count = 0
            
            if material.node_tree and material.node_tree.nodes:
                current_node_count = len(material.node_tree.nodes)
            
            # Compare node count
            if current_node_count != stored_material.get("node_count", 0):
                modified.append(material)
    
    # Find removed materials
    for name in stored_dict:
        if name not in current_dict:
            removed.append(stored_dict[name])
    
    return added, modified, removed


def compare_images(current_images: List, stored_images: List) -> Tuple[List, List, List]:
    """Compare current images with stored images.
    Returns: (added, modified, removed)
    """
    stored_dict = {img["name"]: img for img in stored_images}
    current_dict = {img.name: img for img in current_images}
    
    added = []
    modified = []
    removed = []
    
    # Find added and modified images
    for name, image in current_dict.items():
        if name not in stored_dict:
            added.append(image)
        else:
            stored_image = stored_dict[name]
            
            # Compare size and channels
            current_size = tuple(image.size) if image.size else (0, 0)
            stored_size = tuple(stored_image.get("size", (0, 0)))
            
            if (current_size != stored_size or
                image.channels != stored_image.get("channels", 0)):
                modified.append(image)
    
    # Find removed images
    for name in stored_dict:
        if name not in current_dict:
            removed.append(stored_dict[name])
    
    return added, modified, removed


def compare_texts(current_texts: List, stored_texts: List) -> Tuple[List, List, List]:
    """Compare current texts with stored texts.
    Returns: (added, modified, removed)
    """
    stored_dict = {text["name"]: text for text in stored_texts}
    current_dict = {text.name: text for text in current_texts}
    
    added = []
    modified = []
    removed = []
    
    # Find added and modified texts
    for name, text in current_dict.items():
        if name not in stored_dict:
            added.append(text)
        else:
            stored_text = stored_dict[name]
            
            # Compare content
            current_content = text.as_string()
            stored_content = stored_text.get("content", "")
            
            if current_content != stored_content:
                modified.append(text)
    
    # Find removed texts
    for name in stored_dict:
        if name not in current_dict:
            removed.append(stored_dict[name])
    
    return added, modified, removed


def compare_actions(current_actions: List, stored_actions: List) -> Tuple[List, List, List]:
    """Compare current actions with stored actions.
    Returns: (added, modified, removed)
    """
    stored_dict = {action["name"]: action for action in stored_actions}
    current_dict = {action.name: action for action in current_actions}
    
    added = []
    modified = []
    removed = []
    
    # Find added and modified actions
    for name, action in current_dict.items():
        if name not in stored_dict:
            added.append(action)
        else:
            stored_action = stored_dict[name]
            
            # Compare fcurve count
            if len(action.fcurves) != stored_action.get("fcurve_count", 0):
                modified.append(action)
    
    # Find removed actions
    for name in stored_dict:
        if name not in current_dict:
            removed.append(stored_dict[name])
    
    return added, modified, removed


def compare_node_groups(current_node_groups: List, stored_node_groups: List) -> Tuple[List, List, List]:
    """Compare current node groups with stored node groups.
    Returns: (added, modified, removed)
    """
    stored_dict = {ng["name"]: ng for ng in stored_node_groups}
    current_dict = {ng.name: ng for ng in current_node_groups}
    
    added = []
    modified = []
    removed = []
    
    # Find added and modified node groups
    for name, node_group in current_dict.items():
        if name not in stored_dict:
            added.append(node_group)
        else:
            stored_ng = stored_dict[name]
            
            # Compare node count
            current_node_count = len(node_group.nodes) if node_group.nodes else 0
            stored_node_count = stored_ng.get("node_count", 0)
            
            if current_node_count != stored_node_count:
                modified.append(node_group)
    
    # Find removed node groups
    for name in stored_dict:
        if name not in current_dict:
            removed.append(stored_dict[name])
    
    return added, modified, removed


def get_changes() -> Dict[str, Dict[str, List]]:
    """Get all changes compared to the last commit."""
    try:
        gitblend_dir = get_gitblend_dir()
        metadata = load_commit_metadata(gitblend_dir)
        
        if not metadata.get("commits"):
            return {"error": "No previous commits found"}
        
        # Get the last commit
        current_commit = metadata.get("current_commit")
        if not current_commit or current_commit not in metadata["commits"]:
            return {"error": "No current commit found"}
        
        last_commit_data = metadata["commits"][current_commit]["data_blocks"]
        
        # Get current data blocks
        current_data = {
            "objects": list(bpy.data.objects),
            "meshes": list(bpy.data.meshes),
            "materials": list(bpy.data.materials),
            "images": list(bpy.data.images),
            "texts": list(bpy.data.texts),
            "actions": list(bpy.data.actions),
            "node_groups": list(bpy.data.node_groups)
        }
        
        # Compare each category
        changes = {}
        compare_functions = {
            "objects": compare_objects,
            "meshes": compare_meshes,
            "materials": compare_materials,
            "images": compare_images,
            "texts": compare_texts,
            "actions": compare_actions,
            "node_groups": compare_node_groups
        }
        
        for category, compare_func in compare_functions.items():
            current_items = current_data[category]
            stored_items = last_commit_data.get(category, [])
            
            added, modified, removed = compare_func(current_items, stored_items)
            
            changes[category] = {
                "added": [item.name for item in added],
                "modified": [item.name for item in modified],
                "removed": [item["name"] if isinstance(item, dict) else item.name for item in removed]
            }
        
        return changes
        
    except Exception as e:
        return {"error": str(e)}