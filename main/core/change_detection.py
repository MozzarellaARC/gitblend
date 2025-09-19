"""
ChangeDetectionService - Handles signature comparison and delta detection for GitBlend.

This service centralizes all the logic for:
- Comparing data signatures to detect changes
- Identifying specific changed data blocks
- Calculating change summaries
- Determining what data blocks need to be exported
"""

import bpy
from typing import Dict, Set, Tuple, Any, List
from .signature_service import SignatureService
from .repository_service import RepositoryService
from .export_service import ExportService


class ChangeDetectionService:
    """Service for detecting changes between data signatures."""
    
    @staticmethod
    def detect_changes_and_deltas(parent_hash: str = None) -> Tuple[bool, Dict[str, int], Set]:
        """
        Detect changes and return specific changed data blocks for delta export.
        
        Returns:
            Tuple of (changes_detected, change_summary, changed_data_blocks)
        """
        if not parent_hash:
            # First commit - everything is new, export all
            current_counts = ChangeDetectionService._get_data_block_counts()
            change_summary = {
                "objects": current_counts.get("objects", 0),
                "meshes": current_counts.get("meshes", 0),
                "materials": current_counts.get("materials", 0),
                "images": current_counts.get("images", 0),
                "texts": current_counts.get("texts", 0),
                "actions": current_counts.get("actions", 0),
                "node_groups": current_counts.get("node_groups", 0)
            }
            # For first commit, export everything
            all_data_blocks = ExportService.get_all_data_blocks()
            return True, change_summary, all_data_blocks
        
        # Load previous commit to compare
        previous_signature = RepositoryService.load_signature_file(parent_hash)
        if not previous_signature:
            # Previous signature missing, assume changes, export all
            current_counts = ChangeDetectionService._get_data_block_counts()
            change_summary = {type_name: count for type_name, count in current_counts.items()}
            all_data_blocks = ExportService.get_all_data_blocks()
            return True, change_summary, all_data_blocks
        
        # Create current state signature
        current_signature = SignatureService.generate_data_signature()
        
        # Compare signatures to detect specific changes
        changes_detected, change_summary, changed_data_blocks = ChangeDetectionService._compare_signatures_and_get_deltas(
            current_signature, previous_signature
        )
        
        return changes_detected, change_summary, changed_data_blocks
    
    @staticmethod
    def _compare_signatures_and_get_deltas(current_sig: Dict, previous_sig: Dict) -> Tuple[bool, Dict[str, int], Set]:
        """Compare two data signatures and return changes detected plus specific changed data blocks."""
        changes = {}
        has_changes = False
        changed_data_blocks = set()
        
        # Define data block collections mapping
        data_collections = {
            'objects': bpy.data.objects,
            'meshes': bpy.data.meshes,
            'materials': bpy.data.materials,
            'images': bpy.data.images,
            'texts': bpy.data.texts,
            'actions': bpy.data.actions,
            'node_groups': bpy.data.node_groups
        }
        
        for data_type in ["objects", "meshes", "materials", "images", "texts", "actions", "node_groups"]:
            current_items = current_sig.get(data_type, {})
            previous_items = previous_sig.get(data_type, {})
            collection = data_collections[data_type]
            
            # Find additions, removals, and modifications
            added = set(current_items.keys()) - set(previous_items.keys())
            removed = set(previous_items.keys()) - set(current_items.keys())
            common = set(current_items.keys()) & set(previous_items.keys())
            
            # Check for modifications in common items
            modified = set()
            for item_name in common:
                if current_items[item_name] != previous_items[item_name]:
                    modified.add(item_name)
            
            # Add specific changed data blocks to the set
            for item_name in added | modified:
                # Find the actual data block object
                data_block = collection.get(item_name)
                if data_block:
                    changed_data_blocks.add(data_block)
            
            # Note: We don't export removed items since they don't exist anymore
            
            type_changes = len(added) + len(removed) + len(modified)
            if type_changes > 0:
                has_changes = True
                changes[data_type] = {
                    "added": len(added),
                    "removed": len(removed),
                    "modified": len(modified),
                    "total": type_changes
                }
            else:
                changes[data_type] = {
                    "added": 0,
                    "removed": 0,
                    "modified": 0,
                    "total": 0
                }
        
        # Create summary for display
        change_summary = {}
        for data_type, stats in changes.items():
            if stats["total"] > 0:
                change_summary[data_type] = stats["total"]
        
        return has_changes, change_summary, changed_data_blocks
    
    @staticmethod
    def _get_data_block_counts() -> Dict[str, int]:
        """Get counts of current data blocks."""
        return {
            "objects": len(bpy.data.objects),
            "meshes": len(bpy.data.meshes),
            "materials": len(bpy.data.materials),
            "images": len(bpy.data.images),
            "texts": len(bpy.data.texts),
            "actions": len(bpy.data.actions),
            "node_groups": len(bpy.data.node_groups)
        }
    
    @staticmethod
    def format_change_summary(change_summary: Dict[str, int]) -> str:
        """Format change summary for display."""
        if not change_summary:
            return "No changes"
        
        changes_text = ", ".join([
            f"{count} {type_name}" 
            for type_name, count in change_summary.items() 
            if count > 0
        ])
        
        return changes_text or "No changes"
    
    @staticmethod
    def has_significant_changes(change_summary: Dict[str, int]) -> bool:
        """Check if there are any significant changes worth committing."""
        return any(count > 0 for count in change_summary.values())
    
    @staticmethod
    def get_changed_block_names(changed_data_blocks: Set, limit: int = 50) -> List[str]:
        """Get names of changed data blocks, limited for metadata storage."""
        changed_block_names = [block.name for block in changed_data_blocks if hasattr(block, 'name')]
        return changed_block_names[:limit]
    
    @staticmethod
    def analyze_change_types(changed_data_blocks: Set) -> Dict[str, List[str]]:
        """Analyze what types of changes occurred."""
        change_types = {
            'objects': [],
            'meshes': [],
            'materials': [],
            'images': [],
            'texts': [],
            'actions': [],
            'node_groups': []
        }
        
        for block in changed_data_blocks:
            if not hasattr(block, 'bl_rna'):
                continue
                
            # Determine the type of data block
            if hasattr(block, 'type') and hasattr(block, 'location'):
                # Object
                change_types['objects'].append(block.name)
            elif hasattr(block, 'vertices'):
                # Mesh
                change_types['meshes'].append(block.name)
            elif hasattr(block, 'diffuse_color'):
                # Material
                change_types['materials'].append(block.name)
            elif hasattr(block, 'filepath') and hasattr(block, 'size'):
                # Image
                change_types['images'].append(block.name)
            elif hasattr(block, 'lines'):
                # Text
                change_types['texts'].append(block.name)
            elif hasattr(block, 'fcurves'):
                # Action
                change_types['actions'].append(block.name)
            elif hasattr(block, 'nodes') and hasattr(block, 'links'):
                # Node group
                change_types['node_groups'].append(block.name)
        
        return {k: v for k, v in change_types.items() if v}  # Return only non-empty lists
    
    @staticmethod
    def requires_node_related_export(changed_data_blocks: Set) -> bool:
        """Check if the changes require node-related export strategy."""
        return any(
            hasattr(block, 'bl_rna') and 
            hasattr(block.bl_rna, 'identifier') and 
            block.bl_rna.identifier == 'NodeTree' 
            for block in changed_data_blocks
        )
    
    @staticmethod
    def estimate_export_complexity(changed_data_blocks: Set) -> str:
        """Estimate the complexity of the export operation."""
        block_count = len(changed_data_blocks)
        
        if block_count == 0:
            return "none"
        elif block_count <= 5:
            return "simple"
        elif block_count <= 20:
            return "moderate"
        else:
            return "complex"
    
    @staticmethod
    def get_change_statistics(change_summary: Dict[str, int]) -> Dict[str, Any]:
        """Get detailed statistics about the changes."""
        total_changes = sum(change_summary.values())
        
        stats = {
            "total_changes": total_changes,
            "types_affected": len([k for k, v in change_summary.items() if v > 0]),
            "largest_change_type": max(change_summary.items(), key=lambda x: x[1])[0] if total_changes > 0 else None,
            "largest_change_count": max(change_summary.values()) if total_changes > 0 else 0,
            "change_distribution": change_summary
        }
        
        return stats