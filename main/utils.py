"""Utility functions for git_blend operations."""
import bpy
import json
import hashlib
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple


def get_blend_file_hash() -> str:
    """Generate SHA-256 hash of the current .blend file."""
    if not bpy.data.filepath:
        # If file is not saved, use a default hash
        return hashlib.sha256("unsaved_blend_file".encode()).hexdigest()
    
    with open(bpy.data.filepath, 'rb') as f:
        content = f.read()
        return hashlib.sha256(content).hexdigest()


def generate_tree_hash(serialized_data: Dict[str, Any]) -> str:
    """Generate a hash representing the complete state of all data blocks (tree hash)."""
    # Create a canonical string representation of the complete data state
    tree_data = json.dumps(serialized_data, sort_keys=True)
    return hashlib.sha256(tree_data.encode()).hexdigest()


def generate_commit_hash(message: str, timestamp: float, tree_hash: str, parent_hash: str = None) -> str:
    """Generate a unique commit hash based on message, timestamp, tree hash, and parent hash."""
    # Create a git-like commit data string
    commit_data = f"tree {tree_hash}\n"
    if parent_hash:
        commit_data += f"parent {parent_hash}\n"
    commit_data += f"timestamp {timestamp}\n"
    commit_data += f"message {message}"
    
    return hashlib.sha256(commit_data.encode()).hexdigest()


def get_gitblend_dir() -> Path:
    """Get the .gitblend directory path for the current .blend file."""
    if not bpy.data.filepath:
        raise ValueError("Blend file must be saved before initializing git_blend")
    
    blend_dir = Path(bpy.data.filepath).parent
    return blend_dir / ".gitblend"


def ensure_gitblend_dir() -> Path:
    """Ensure the .gitblend directory exists and return its path."""
    gitblend_dir = get_gitblend_dir()
    gitblend_dir.mkdir(exist_ok=True)
    return gitblend_dir


def sample_mesh_vertices(mesh: bpy.types.Mesh, max_vertices: int = 1000) -> List[Tuple[float, float, float]]:
    """Sample vertices from a mesh for comparison purposes."""
    vertices = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
    if len(vertices) <= max_vertices:
        return vertices
    
    # Sample evenly across the vertex array
    step = len(vertices) // max_vertices
    return vertices[::step][:max_vertices]


def get_data_block_info(data_block) -> Dict[str, Any]:
    """Get serializable information about a data block."""
    info = {
        "name": data_block.name,
        "type": type(data_block).__name__
    }
    
    # Add type-specific information
    if hasattr(data_block, 'vertices'):  # Mesh
        info["vertex_count"] = len(data_block.vertices)
        info["face_count"] = len(data_block.polygons)
        info["vertices_sample"] = sample_mesh_vertices(data_block)
    elif hasattr(data_block, 'size'):  # Image
        info["size"] = tuple(data_block.size)
        info["channels"] = data_block.channels
    elif hasattr(data_block, 'as_string'):  # Text
        info["content"] = data_block.as_string()
        info["lines"] = len(data_block.lines)
    elif hasattr(data_block, 'fcurves'):  # Action
        info["fcurve_count"] = len(data_block.fcurves)
    elif hasattr(data_block, 'nodes'):  # NodeGroup/Material with nodes
        info["node_count"] = len(data_block.nodes) if data_block.nodes else 0
    elif hasattr(data_block, 'node_tree') and data_block.node_tree:  # Material
        info["node_count"] = len(data_block.node_tree.nodes)
    
    return info


def export_data_blocks_to_blend(gitblend_dir: Path, file_hash: str, data_blocks: List) -> str:
    """Export data blocks to a .blend file using bpy.data.libraries.write."""
    blend_filename = f"{file_hash}.blend"
    blend_filepath = gitblend_dir / blend_filename
    
    # Create a set of data blocks to export (bpy.data.libraries.write expects a set)
    data_blocks_to_export = {db for db in data_blocks if db is not None}
    
    if data_blocks_to_export:
        bpy.data.libraries.write(str(blend_filepath), data_blocks_to_export)
    
    return str(blend_filepath)


def serialize_data_blocks(data_blocks_dict: Dict[str, List]) -> Dict[str, Any]:
    """Serialize data blocks information to JSON format."""
    serialized = {}
    
    for category, blocks in data_blocks_dict.items():
        serialized[category] = []
        for block in blocks:
            if block is not None:
                block_info = get_data_block_info(block)
                serialized[category].append(block_info)
    
    return serialized


def load_commit_metadata(gitblend_dir: Path) -> Dict[str, Any]:
    """Load commit metadata from JSON file."""
    metadata_file = gitblend_dir / "commits.json"
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            return json.load(f)
    return {"commits": {}, "version": 1}


def save_commit_metadata(gitblend_dir: Path, metadata: Dict[str, Any]) -> None:
    """Save commit metadata to JSON file."""
    metadata_file = gitblend_dir / "commits.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)