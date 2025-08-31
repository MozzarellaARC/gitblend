"""
Shared collection and object operations to reduce code duplication.
Contains common patterns for iterating, mapping, and manipulating collections and objects.
"""
import re
from typing import Dict, Iterable, List, Optional, Tuple
import bpy


# Regex for extracting UIDs from snapshot names
UID_RE = re.compile(r"_(\d{10,20})(?:-\d+)?$")


def iter_objects_recursive(coll: bpy.types.Collection) -> Iterable[bpy.types.Object]:
    """Iterate over all objects in a collection and its children recursively."""
    for obj in coll.objects:
        yield obj
    for child in coll.children:
        yield from iter_objects_recursive(child)


def extract_original_name(id_block) -> Optional[str]:
    """Extract the original name from an object or collection, falling back to base name."""
    try:
        v = id_block.get("gitblend_orig_name", None)
        if isinstance(v, str) and v:
            return v
    except Exception:
        pass
    # Fallback: strip UID suffix
    name = getattr(id_block, "name", "") or ""
    m = UID_RE.search(name)
    return name[:m.start()] if m else name


def build_name_map(coll: bpy.types.Collection, snapshot: bool = False) -> Dict[str, bpy.types.Object]:
    """Build a mapping from object names to objects.
    
    Args:
        coll: Collection to map
        snapshot: If True, use stored original names; if False, use current names
    
    Returns:
        Dict mapping names to objects (first occurrence wins for duplicates)
    """
    name_map: Dict[str, bpy.types.Object] = {}
    for obj in iter_objects_recursive(coll):
        name = extract_original_name(obj) if snapshot else (obj.name or "")
        if name and name not in name_map:
            name_map[name] = obj
    return name_map


def find_containing_collection(root_coll: bpy.types.Collection, target_obj: bpy.types.Object) -> Optional[bpy.types.Collection]:
    """Find the collection that directly contains the target object."""
    # Check if target_obj is directly in this collection
    for obj in root_coll.objects:
        if obj == target_obj:
            return root_coll
    
    # Search in child collections
    for child in root_coll.children:
        found = find_containing_collection(child, target_obj)
        if found:
            return found
    return None


def path_to_collection(root_coll: bpy.types.Collection, target_coll: bpy.types.Collection) -> List[bpy.types.Collection]:
    """Find the path from root collection to target collection."""
    path = []
    found = False
    
    def dfs(c: bpy.types.Collection, acc: List[bpy.types.Collection]):
        nonlocal path, found
        if found:
            return
        acc.append(c)
        if c == target_coll:
            path = list(acc)
            found = True
        else:
            for ch in c.children:
                dfs(ch, acc)
                if found:
                    break
        acc.pop()
    
    dfs(root_coll, [])
    return path if found else []


def list_branch_snapshots(scene: bpy.types.Scene, branch: str, max_uid: Optional[str] = None) -> List[bpy.types.Collection]:
    """List all snapshot collections for a branch, optionally up to a maximum UID.
    
    Args:
        scene: Blender scene
        branch: Branch name to filter by
        max_uid: If provided, only include snapshots with UID <= max_uid
    
    Returns:
        List of snapshot collections, sorted by UID descending (newest first)
    """
    # Find .gitblend collection
    dot_coll = None
    for c in scene.collection.children:
        if c.name == ".gitblend":
            dot_coll = c
            break
    
    if not dot_coll:
        return []
    
    items: List[Tuple[str, bpy.types.Collection]] = []
    for c in dot_coll.children:
        name = c.name or ""
        if not name.startswith(branch):
            continue
        
        match = UID_RE.search(name)
        uid = match.group(1) if match else ""
        if not uid:
            continue
        
        # Filter by max_uid if provided
        if max_uid is not None and uid > max_uid:
            continue
        
        items.append((uid, c))
    
    # Sort by UID descending (newest first)
    items.sort(key=lambda t: t[0], reverse=True)
    return [c for _, c in items]


def ensure_mirrored_collection_path(source_coll: bpy.types.Collection, 
                                   snapshot_path: List[bpy.types.Collection]) -> bpy.types.Collection:
    """Ensure a mirrored collection path exists under source collection.
    
    Creates nested collections as needed to mirror the structure from the snapshot.
    
    Args:
        source_coll: Root collection to create structure under
        snapshot_path: Path of collections from snapshot (first is root, rest are children)
    
    Returns:
        The final collection in the mirrored path
    """
    dest = source_coll
    # Skip the first item in path as it's the root
    for snap_coll in snapshot_path[1:]:
        name = extract_original_name(snap_coll)
        
        # Look for existing child with this name
        existing = None
        for child in dest.children:
            if child.name == name:
                existing = child
                break
        
        if existing is None:
            try:
                new_coll = bpy.data.collections.new(name)
                dest.children.link(new_coll)
                dest = new_coll
            except Exception:
                # If creation fails, fallback to current dest
                break
        else:
            dest = existing
    
    return dest


def get_dotgitblend_collection(scene: bpy.types.Scene) -> Optional[bpy.types.Collection]:
    """Get the .gitblend collection if it exists."""
    for c in scene.collection.children:
        if c.name == ".gitblend":
            return c
    return None


def copy_object_with_data(obj: bpy.types.Object, new_name_suffix: str = "") -> bpy.types.Object:
    """Copy an object including its data, with optional name suffix."""
    dup = obj.copy()
    
    # Copy data if it exists
    if getattr(obj, "data", None) is not None:
        try:
            dup.data = obj.data.copy()
        except Exception:
            pass
    
    # Set new name if suffix provided
    if new_name_suffix:
        try:
            dup.name = f"{obj.name}_{new_name_suffix}"
        except Exception:
            pass
    
    # Store original name metadata
    try:
        dup["gitblend_orig_name"] = obj.name
    except Exception:
        pass
    
    return dup


def unlink_and_remove_object(obj: bpy.types.Object) -> bool:
    """Safely unlink and remove an object from all collections and data.
    
    Returns:
        True if successful, False if there was an error
    """
    try:
        # Unlink from all collections
        for col in list(obj.users_collection):
            try:
                col.objects.unlink(obj)
            except Exception:
                pass
        
        # Remove from data
        bpy.data.objects.remove(obj, do_unlink=True)
        return True
    except Exception:
        return False


def set_object_parent_safely(child: bpy.types.Object, parent: Optional[bpy.types.Object]) -> bool:
    """Safely set object parent relationship.
    
    Returns:
        True if successful, False if there was an error
    """
    try:
        child.parent = parent
        return True
    except Exception:
        return False
