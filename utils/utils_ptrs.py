"""
Pointer remapping utilities for Git Blend addon.

This module handles the complex task of remapping object references (pointers) when
objects are duplicated, restored from snapshots, or moved between scenes.

The main challenge is that Blender uses direct object references, but when we restore
objects from snapshots or handle duplicates, we need to update these references to
point to the correct objects in the current context.
"""

import bpy # type: ignore
import re
from typing import Dict, Optional, Set
from .utils import build_name_map, iter_objects_recursive


# -----------------------------
# Name Processing
# -----------------------------

def get_original_name_from_string(name: str) -> str:
    """Extract original name by removing various suffixes (snapshots, duplicates, etc.)."""
    if not name:
        return ""
    
    # Remove snapshot naming suffixes like _20231201120000 or _20231201120000-1
    m = re.search(r"_(\d{10,20})(?:-\d+)?$", name)
    if m:
        return name[:m.start()]
    
    # Remove Blender duplicate suffixes like .001, .002, etc.
    # Also handle complex duplicates like .001.001
    m = re.search(r"\.(\d{3})(?:\.(\d{3}))*$", name)
    if m:
        return name[:m.start()]
    
    return name


def _get_reference_name(target_obj: bpy.types.Object) -> str:
    """Get the best name to use for finding a replacement object."""
    if not target_obj:
        return ""
    
    # Try original name first (for gitblend snapshot objects)
    try:
        orig_name = target_obj.get("gitblend_orig_name", "")
        if orig_name:
            return orig_name
    except Exception:
        pass
    
    # For regular objects, use current name
    # But also consider if this object might be from the gitblend scene
    current_name = target_obj.name or ""
    
    # If the target object is in a gitblend scene, we probably want to find 
    # the corresponding object in the current working set
    try:
        if target_obj.users_scene:
            for scene in target_obj.users_scene:
                if scene.name == "gitblend":
                    # This object is from the gitblend scene, so we want to find
                    # the corresponding object in the main scene
                    # Remove any snapshot suffixes to get the base name
                    return get_original_name_from_string(current_name)
    except Exception:
        pass
    
    return current_name


# -----------------------------
# Object Resolution
# -----------------------------

def _find_replacement_object(target_name: str, new_objects: Dict[str, bpy.types.Object], 
                           existing_objects: Dict[str, bpy.types.Object], 
                           requesting_obj: Optional[bpy.types.Object] = None) -> Optional[bpy.types.Object]:
    """Find replacement object, preferring new objects over existing ones.
    
    Args:
        target_name: Name of object to find
        new_objects: Recently restored/created objects
        existing_objects: Objects that were already in the scene
        requesting_obj: The object that needs this reference (for smarter mapping)
    """
    if not target_name:
        return None
    
    # 1. Direct match in new objects first (restored/duplicated objects)
    if target_name in new_objects:
        return new_objects[target_name]
    
    # 2. Try to find by original name in new objects (for gitblend snapshot objects)
    for obj in (new_objects or {}).values():
        try:
            orig_name = obj.get("gitblend_orig_name", "")
            if orig_name and orig_name == target_name:
                return obj
        except Exception:
            pass
    
    # 3. Smart duplicate handling: if requesting object is a duplicate (e.g., "Cube.001")
    # and target is the base name (e.g., "Cube"), prefer a restored base object
    if requesting_obj:
        requesting_name = requesting_obj.name
        requesting_base = get_original_name_from_string(requesting_name)
        target_base = get_original_name_from_string(target_name)
        
        # If requesting object is a duplicate (.001, .002, etc.) looking for base object
        if (requesting_name != requesting_base and target_name == target_base and 
            requesting_base == target_base):
            # Look for the base object in new_objects (restored objects) first
            if target_base in new_objects:
                return new_objects[target_base]
    
    # 4. Handle Blender's duplicate naming pattern (e.g., Cube -> Cube.001, Cube.002)
    # If target is a base name like "Cube", prefer any restored version in new_objects
    base_target_name = get_original_name_from_string(target_name)
    if base_target_name == target_name:  # target_name is already a base name
        # Look for any duplicates of this base name in new_objects first
        for name, obj in (new_objects or {}).items():
            if name.startswith(target_name + ".") and len(name) > len(target_name) + 1:
                suffix = name[len(target_name)+1:]
                if suffix.isdigit() or (suffix.count('.') == 2 and all(part.isdigit() for part in suffix.split('.'))):
                    return obj
            # Also check gitblend_orig_name for duplicates
            try:
                orig_name = obj.get("gitblend_orig_name", "")
                if orig_name and (orig_name == target_name or 
                                (orig_name.startswith(target_name + ".") and 
                                 len(orig_name) > len(target_name) + 1)):
                    suffix = orig_name[len(target_name)+1:]
                    if suffix.isdigit() or (suffix.count('.') == 2 and all(part.isdigit() for part in suffix.split('.'))):
                        return obj
            except Exception:
                pass
    
    # 5. Fall back to existing objects
    if target_name in existing_objects:
        return existing_objects[target_name]
    
    # 6. Try to find by original name in existing objects
    for obj in (existing_objects or {}).values():
        try:
            orig_name = obj.get("gitblend_orig_name", "")
            if orig_name and orig_name == target_name:
                return obj
        except Exception:
            pass
    
    # 7. Last resort: try base name variations
    if base_target_name != target_name:
        # Try the base name
        if base_target_name in new_objects:
            return new_objects[base_target_name]
        if base_target_name in existing_objects:
            return existing_objects[base_target_name]
    
    return None


# -----------------------------
# Object Pointer Remapping
# -----------------------------

def remap_object_pointers(obj: bpy.types.Object, new_objects: Dict[str, bpy.types.Object], 
                        existing_objects: Dict[str, bpy.types.Object]) -> None:
    """Remap all object pointers for a single object."""
    if not obj:
        return
    
    # Remap parent relationship
    try:
        if obj.parent:
            parent_name = obj.parent.name
            # Also try original name if it exists
            try:
                parent_orig_name = obj.parent.get("gitblend_orig_name", "")
                if parent_orig_name:
                    parent_name = parent_orig_name
            except Exception:
                pass
            
            new_parent = _find_replacement_object(parent_name, new_objects, existing_objects, obj)
            if new_parent and new_parent != obj.parent:
                obj.parent = new_parent
    except Exception:
        pass
    
    # Remap modifier object references
    _remap_modifier_pointers(obj, new_objects, existing_objects)
    
    # Remap constraint targets
    _remap_constraint_pointers(obj, new_objects, existing_objects)


def _remap_modifier_pointers(obj: bpy.types.Object, new_objects: Dict[str, bpy.types.Object], 
                           existing_objects: Dict[str, bpy.types.Object]) -> None:
    """Remap modifier object references."""
    try:
        for modifier in obj.modifiers:
            # Mirror modifier
            if modifier.type == 'MIRROR' and hasattr(modifier, 'mirror_object'):
                if modifier.mirror_object:
                    target_name = _get_reference_name(modifier.mirror_object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.mirror_object = new_target
                        modifier.use_mirror_object = True
            
            # Array modifier
            elif modifier.type == 'ARRAY' and hasattr(modifier, 'offset_object'):
                if modifier.offset_object:
                    target_name = _get_reference_name(modifier.offset_object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.offset_object = new_target
            
            # Boolean modifier
            elif modifier.type in ['BOOLEAN', 'INTERSECT', 'UNION', 'DIFFERENCE'] and hasattr(modifier, 'object'):
                if modifier.object:
                    target_name = _get_reference_name(modifier.object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.object = new_target
            
            # Armature modifier
            elif modifier.type == 'ARMATURE' and hasattr(modifier, 'object'):
                if modifier.object:
                    target_name = _get_reference_name(modifier.object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.object = new_target
            
            # Curve modifier
            elif modifier.type in ['CURVE', 'FOLLOW_PATH'] and hasattr(modifier, 'object'):
                if modifier.object:
                    target_name = _get_reference_name(modifier.object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.object = new_target
                        
            # Shrinkwrap modifier
            elif modifier.type == 'SHRINKWRAP' and hasattr(modifier, 'target'):
                if modifier.target:
                    target_name = _get_reference_name(modifier.target)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.target = new_target
                        
            # Surface Deform modifier
            elif modifier.type == 'SURFACE_DEFORM' and hasattr(modifier, 'target'):
                if modifier.target:
                    target_name = _get_reference_name(modifier.target)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.target = new_target
    except Exception:
        pass


def _remap_constraint_pointers(obj: bpy.types.Object, new_objects: Dict[str, bpy.types.Object], 
                             existing_objects: Dict[str, bpy.types.Object]) -> None:
    """Remap constraint target objects."""
    try:
        for constraint in obj.constraints:
            if hasattr(constraint, 'target') and constraint.target:
                target_name = _get_reference_name(constraint.target)
                new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                if new_target:
                    constraint.target = new_target
    except Exception:
        pass


def remap_references_for_objects(new_objects: Dict[str, bpy.types.Object], 
                               existing_objects: Dict[str, bpy.types.Object]) -> None:
    """Remap object pointers on all provided objects."""
    
    for obj in (new_objects or {}).values():
        try:
            remap_object_pointers(obj, new_objects, existing_objects)
        except Exception:
            continue


# -----------------------------
# Scene-Level Remapping
# -----------------------------

def remap_scene_pointers(source: bpy.types.Collection, new_objects: Dict[str, bpy.types.Object]) -> None:
    """Remap all object pointers in a scene after restoration/duplication."""
    try:
        existing_objects = build_name_map(source, snapshot=False)
        
        # Remap pointers in new objects
        for obj in (new_objects or {}).values():
            try:
                remap_object_pointers(obj, new_objects, existing_objects)
            except Exception:
                continue
        
        # Remap pointers in existing objects (excluding the new ones to avoid double-processing)
        for name, obj in list(existing_objects.items()):
            if name not in new_objects:
                try:
                    remap_object_pointers(obj, new_objects, existing_objects)
                except Exception:
                    pass
    except Exception:
        pass


# -----------------------------
# Dependency Analysis
# -----------------------------

def get_object_dependencies(obj: bpy.types.Object) -> Set[str]:
    """Get names of objects that this object depends on."""
    dependencies = set()
    
    # Parent dependency
    try:
        if obj.parent:
            dependencies.add(obj.parent.name)
    except Exception:
        pass
    
    # Modifier dependencies (most common cases)
    try:
        for modifier in obj.modifiers:
            if modifier.type == 'MIRROR' and hasattr(modifier, 'mirror_object'):
                if modifier.mirror_object:
                    dependencies.add(modifier.mirror_object.name)
            elif modifier.type == 'ARRAY' and hasattr(modifier, 'offset_object'):
                if modifier.offset_object:
                    dependencies.add(modifier.offset_object.name)
            elif modifier.type == 'ARMATURE' and hasattr(modifier, 'object'):
                if modifier.object:
                    dependencies.add(modifier.object.name)
            elif modifier.type in ['CURVE', 'FOLLOW_PATH'] and hasattr(modifier, 'object'):
                if modifier.object:
                    dependencies.add(modifier.object.name)
            elif modifier.type in ['BOOLEAN', 'INTERSECT', 'UNION', 'DIFFERENCE'] and hasattr(modifier, 'object'):
                if modifier.object:
                    dependencies.add(modifier.object.name)
            elif modifier.type == 'SHRINKWRAP' and hasattr(modifier, 'target'):
                if modifier.target:
                    dependencies.add(modifier.target.name)
            elif modifier.type == 'SURFACE_DEFORM' and hasattr(modifier, 'target'):
                if modifier.target:
                    dependencies.add(modifier.target.name)
    except Exception:
        pass
    
    # Constraint dependencies
    try:
        for constraint in obj.constraints:
            if hasattr(constraint, 'target') and constraint.target:
                dependencies.add(constraint.target.name)
    except Exception:
        pass
    
    return dependencies
