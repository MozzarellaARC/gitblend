"""
Simplified Content-Addressed Storage for Git Blend
Focus: Lightweight commit metadata and fast history operations
"""
import os
import json
import hashlib
from typing import Dict, Optional, List, Tuple


def _project_root_dir() -> str:
    """Get the project root directory."""
    try:
        import bpy  # type: ignore
        root = bpy.path.abspath("//") or os.getcwd()
        return root
    except Exception:
        return os.getcwd()


def _store_root() -> str:
    """Get the .gitblend store root directory."""
    return os.path.join(_project_root_dir(), ".gitblend")


def _commits_dir() -> str:
    """Directory for commit metadata files."""
    return os.path.join(_store_root(), "commits")


def _refs_dir() -> str:
    """Directory for branch references."""
    return os.path.join(_store_root(), "refs", "heads")


def _ensure_dirs():
    """Create necessary directories."""
    os.makedirs(_commits_dir(), exist_ok=True)
    os.makedirs(_refs_dir(), exist_ok=True)


def _sha256_text(text: str) -> str:
    """Generate SHA256 hash of text."""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _canonical_dumps(data: Dict) -> str:
    """Create canonical JSON string for consistent hashing."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _write_json_atomic(path: str, data: Dict) -> None:
    """Write JSON file atomically using temporary file."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


def _read_json(path: str) -> Optional[Dict]:
    """Read JSON file safely."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ===================== Core Commit Operations =====================

def create_commit(branch: str, uid: str, timestamp: str, message: str, 
                 changed_objects: List[str], snapshot_uid: str) -> str:
    """
    Create a lightweight commit focused on metadata and history.
    
    Args:
        branch: Branch name
        uid: Unique timestamp identifier
        timestamp: Human-readable timestamp
        message: Commit message
        changed_objects: List of object names that changed
        snapshot_uid: UID linking to visual snapshot in Blender
    
    Returns:
        commit_id: SHA256 hash of the commit
    """
    _ensure_dirs()
    
    # Get parent commit
    parent = read_ref(branch)
    
    # Create lightweight commit metadata
    commit_data = {
        "version": "2.0",  # Simplified version
        "uid": uid,
        "timestamp": timestamp,
        "message": message,
        "branch": branch,
        "parent": parent,
        "changed_objects": sorted(changed_objects),
        "snapshot_uid": snapshot_uid,  # Links to visual snapshot
        "object_count": len(changed_objects)
    }
    
    # Generate deterministic commit ID
    commit_id = _sha256_text(_canonical_dumps(commit_data))
    
    # Store commit
    commit_path = os.path.join(_commits_dir(), f"{commit_id}.json")
    if not os.path.exists(commit_path):  # Only write if doesn't exist
        _write_json_atomic(commit_path, commit_data)
    
    # Update branch reference
    update_ref(branch, commit_id)
    
    return commit_id


def read_commit(commit_id: str) -> Optional[Dict]:
    """Read commit by ID."""
    if not commit_id:
        return None
    commit_path = os.path.join(_commits_dir(), f"{commit_id}.json")
    return _read_json(commit_path)


def get_commit_objects(commit_id: str) -> List[str]:
    """Get list of changed objects for a commit."""
    commit = read_commit(commit_id)
    if not commit:
        return []
    return commit.get("changed_objects", [])


def get_commit_snapshot_uid(commit_id: str) -> Optional[str]:
    """Get the snapshot UID linked to this commit."""
    commit = read_commit(commit_id)
    if not commit:
        return None
    return commit.get("snapshot_uid")


# ===================== Branch References =====================

def read_ref(branch: str) -> Optional[str]:
    """Read branch reference (HEAD commit ID)."""
    try:
        ref_path = os.path.join(_refs_dir(), branch)
        if os.path.exists(ref_path):
            with open(ref_path, "r", encoding="utf-8") as f:
                return f.read().strip() or None
    except Exception:
        pass
    return None


def update_ref(branch: str, commit_id: str) -> None:
    """Update branch reference to point to commit."""
    _ensure_dirs()
    ref_path = os.path.join(_refs_dir(), branch)
    tmp_path = ref_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(commit_id)
        os.replace(tmp_path, ref_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ===================== History Operations =====================

def get_branch_commits(branch: str, limit: int = 100) -> List[Tuple[str, Dict]]:
    """
    Get commit history for a branch (fast metadata operation).
    
    Returns:
        List of (commit_id, commit_data) tuples in reverse chronological order
    """
    commits = []
    seen = set()
    current = read_ref(branch)
    
    while current and current not in seen and len(commits) < limit:
        seen.add(current)
        commit_data = read_commit(current)
        if not commit_data:
            break
        
        commits.append((current, commit_data))
        current = commit_data.get("parent")
    
    return commits


def get_commits_between(branch: str, from_uid: str, to_uid: str) -> List[Tuple[str, Dict]]:
    """Get commits between two UIDs (exclusive of from_uid, inclusive of to_uid)."""
    commits = get_branch_commits(branch)
    result = []
    found_to = False
    
    for commit_id, commit_data in commits:
        commit_uid = commit_data.get("uid", "")
        
        if commit_uid == to_uid:
            found_to = True
            result.append((commit_id, commit_data))
        elif found_to and commit_uid == from_uid:
            break
        elif found_to:
            result.append((commit_id, commit_data))
    
    return result


def find_commit_by_uid(branch: str, uid: str) -> Optional[Tuple[str, Dict]]:
    """Find commit by UID in branch history."""
    commits = get_branch_commits(branch)
    for commit_id, commit_data in commits:
        if commit_data.get("uid") == uid:
            return (commit_id, commit_data)
    return None


def get_changed_objects_between_commits(branch: str, from_uid: str, to_uid: str) -> List[str]:
    """Get all objects that changed between two commits (fast metadata operation)."""
    commits = get_commits_between(branch, from_uid, to_uid)
    changed = set()
    
    for _, commit_data in commits:
        changed_objects = commit_data.get("changed_objects", [])
        changed.update(changed_objects)
    
    return sorted(list(changed))


# ===================== Backward Compatibility =====================

def get_latest_commit_objects(branch: str) -> Optional[Tuple[str, Dict, Dict[str, str]]]:
    """
    Backward compatibility function.
    Returns (commit_id, commit_data, object_names_map) where object_names_map
    is a simple dict of {object_name: object_name} for compatibility.
    """
    commits = get_branch_commits(branch, limit=1)
    if not commits:
        return None
    
    commit_id, commit_data = commits[0]
    changed_objects = commit_data.get("changed_objects", [])
    
    # Simple object map for compatibility
    object_map = {name: name for name in changed_objects}
    
    return commit_id, commit_data, object_map


def resolve_commit_by_uid(branch: str, uid: str) -> Optional[Tuple[str, Dict]]:
    """Backward compatibility wrapper for find_commit_by_uid."""
    return find_commit_by_uid(branch, uid)


def list_branch_commits(branch: str, limit: int = 100) -> List[Tuple[str, Dict]]:
    """Backward compatibility wrapper for get_branch_commits."""
    return get_branch_commits(branch, limit)
