"""
Snapshot management operations.
Consolidates logic for creating, finding, and managing snapshots.
"""
from typing import Dict, List, Optional, Set, Tuple
import bpy
from .manager_collection import (
    build_name_map, 
    copy_object_with_data, 
    find_containing_collection,
    path_to_collection,
    ensure_mirrored_collection_path,
    iter_objects_recursive
)
from .validate import (
    unique_coll_name,
    unique_obj_name
)


class SnapshotManager:
    """Manages snapshot operations with reusable methods."""
    
    @staticmethod
    def find_snapshot_object_and_destination(
        name: str, 
        snapshot_roots: List[bpy.types.Collection],
        source_coll: bpy.types.Collection
    ) -> Tuple[Optional[bpy.types.Object], bpy.types.Collection]:
        """Find an object by name in snapshots and determine its destination collection.
        
        Args:
            name: Object name to find
            snapshot_roots: List of snapshot collections to search (newest first)
            source_coll: Source collection to mirror structure under
        
        Returns:
            Tuple of (found_object, destination_collection)
        """
        for root in snapshot_roots:
            name_map = build_name_map(root, snapshot=True)
            obj = name_map.get(name)
            if obj is None:
                continue
            
            # Find containing collection and mirror path
            containing_coll = find_containing_collection(root, obj)
            if containing_coll:
                path = path_to_collection(root, containing_coll)
                dest = ensure_mirrored_collection_path(source_coll, path) if path else source_coll
            else:
                dest = source_coll
            
            return obj, dest
        
        return None, source_coll
    
    @staticmethod
    def create_differential_snapshot(
        src: bpy.types.Collection,
        parent_dot: bpy.types.Collection,
        uid: str,
        changed_names: Set[str]
    ) -> Tuple[bpy.types.Collection, Dict[str, bpy.types.Object]]:
        """Create a differential snapshot containing only changed objects.
        
        Args:
            src: Source collection to snapshot
            parent_dot: Parent .gitblend collection
            uid: Unique identifier for snapshot
            changed_names: Set of object names that have changed
        
        Returns:
            Tuple of (new_snapshot_collection, name_to_object_map)
        """
        # Create main snapshot collection
        new_coll = bpy.data.collections.new(unique_coll_name(src.name, uid))
        parent_dot.children.link(new_coll)
        
        # Store metadata
        try:
            new_coll["gitblend_uid"] = uid
            new_coll["gitblend_orig_name"] = src.name
        except Exception:
            pass
        
        name_to_new_obj: Dict[str, bpy.types.Object] = {}
        copied_names: Set[str] = set()
        
        # Build parent relationships from source
        parent_of: Dict[str, Optional[str]] = {}
        for obj in iter_objects_recursive(src):
            name = obj.name or ""
            if name:
                parent_of[name] = obj.parent.name if obj.parent else None
        
        # Propagate changes to descendants
        changed_stable = False
        while not changed_stable:
            before = len(changed_names)
            for name, parent_name in list(parent_of.items()):
                if parent_name and parent_name in changed_names and name not in changed_names:
                    changed_names.add(name)
            changed_stable = len(changed_names) == before
        
        # Copy changed objects
        SnapshotManager._copy_changed_objects_recursive(
            src, new_coll, uid, changed_names, name_to_new_obj, copied_names
        )
        
        # Fix parenting for copied objects
        SnapshotManager._fix_object_parenting(copied_names, name_to_new_obj, parent_of)
        
        return new_coll, name_to_new_obj
    
    @staticmethod
    def _copy_changed_objects_recursive(
        src_coll: bpy.types.Collection,
        dest_coll: bpy.types.Collection, 
        uid: str,
        changed_names: Set[str],
        name_to_new_obj: Dict[str, bpy.types.Object],
        copied_names: Set[str]
    ) -> None:
        """Recursively copy changed objects to destination collection."""
        # Copy objects at this level
        for obj in src_coll.objects:
            name = obj.name or ""
            if not name or name not in changed_names:
                continue
            
            dup = copy_object_with_data(obj)
            dup.name = unique_obj_name(obj.name, uid)
            dest_coll.objects.link(dup)
            
            name_to_new_obj[name] = dup
            copied_names.add(name)
        
        # Recurse into children that have changes
        for child in src_coll.children:
            if SnapshotManager._subtree_has_changes(child, changed_names):
                # Create child collection
                child_coll = bpy.data.collections.new(unique_coll_name(child.name, uid))
                dest_coll.children.link(child_coll)
                
                try:
                    child_coll["gitblend_uid"] = uid
                    child_coll["gitblend_orig_name"] = child.name
                except Exception:
                    pass
                
                SnapshotManager._copy_changed_objects_recursive(
                    child, child_coll, uid, changed_names, name_to_new_obj, copied_names
                )
    
    @staticmethod
    def _subtree_has_changes(coll: bpy.types.Collection, changed_names: Set[str]) -> bool:
        """Check if a collection subtree contains any changed objects."""
        for obj in iter_objects_recursive(coll):
            if (obj.name or "") in changed_names:
                return True
        return False
    
    @staticmethod
    def _fix_object_parenting(
        copied_names: Set[str],
        name_to_new_obj: Dict[str, bpy.types.Object],
        parent_of: Dict[str, Optional[str]]
    ) -> None:
        """Fix parent relationships for copied objects."""
        for name in copied_names:
            dup = name_to_new_obj.get(name)
            if not dup:
                continue
            
            parent_name = parent_of.get(name)
            if not parent_name:
                try:
                    dup.parent = None
                except Exception:
                    pass
                continue
            
            target_parent = name_to_new_obj.get(parent_name)
            if target_parent:
                try:
                    dup.parent = target_parent
                except Exception:
                    pass
            else:
                try:
                    dup.parent = None
                except Exception:
                    pass
    
    @staticmethod
    def restore_objects_from_snapshots(
        desired_objects: List[Dict],
        source_coll: bpy.types.Collection,
        snapshot_roots: List[bpy.types.Collection]
    ) -> Tuple[int, int, int]:
        """Restore objects from snapshots to match desired state.
        
        Args:
            desired_objects: List of object data from commit
            source_coll: Source collection to restore into
            snapshot_roots: Snapshot collections to search for objects
        
        Returns:
            Tuple of (restored_count, skipped_count, removed_count)
        """
        desired_names = [obj.get("name", "") for obj in desired_objects if obj.get("name")]
        desired_parent = {obj.get("name", ""): obj.get("parent", "") for obj in desired_objects if obj.get("name")}
        
        # Get current objects
        current_map = build_name_map(source_coll, snapshot=False)
        
        # Remove objects not in desired set
        removed_count = 0
        for name, obj in list(current_map.items()):
            if name not in desired_names:
                from .manager_collection import unlink_and_remove_object
                if unlink_and_remove_object(obj):
                    removed_count += 1
        
        # Rebuild current map after removals
        current_map = build_name_map(source_coll, snapshot=False)
        
        # Restore desired objects
        new_objects = {}
        old_objects = {}
        
        for name in desired_names:
            snap_obj, dest_coll = SnapshotManager.find_snapshot_object_and_destination(
                name, snapshot_roots, source_coll
            )
            
            if not snap_obj:
                continue
            
            # Create duplicate
            dup = copy_object_with_data(snap_obj, "restored")
            current_obj = current_map.get(name)
            
            if current_obj:
                old_objects[name] = current_obj
            
            # Link to destination
            try:
                dest_coll.objects.link(dup)
            except Exception:
                # Fallback to source collection
                try:
                    source_coll.objects.link(dup)
                except Exception:
                    continue
            
            new_objects[name] = dup
        
        # Set up parenting
        SnapshotManager._fix_object_parenting(
            set(new_objects.keys()), new_objects, desired_parent
        )
        
        # Remove old objects
        for name in desired_names:
            old_obj = old_objects.get(name)
            if old_obj:
                from .manager_collection import unlink_and_remove_object
                unlink_and_remove_object(old_obj)
        
        # Rename restored objects to final names
        for name, dup in new_objects.items():
            try:
                dup.name = name
            except Exception:
                pass
        
        restored_count = len(new_objects)
        skipped_count = max(0, len(desired_names) - restored_count)
        
        return restored_count, skipped_count, removed_count
