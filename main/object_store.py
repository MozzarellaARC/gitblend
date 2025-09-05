import os
import json
import hashlib
from typing import Dict, Tuple, Optional


def _project_root_dir() -> str:
    # Avoid importing bpy here; rely on caller paths. Fallback to CWD.
    try:
        import bpy  # type: ignore
        root = bpy.path.abspath("//") or os.getcwd()
        return root
    except Exception:
        return os.getcwd()


def _store_root() -> str:
    return os.path.join(_project_root_dir(), ".gitblend")


def _objects_dir() -> str:
    return os.path.join(_store_root(), "objects")


def _refs_dir() -> str:
    return os.path.join(_store_root(), "refs", "heads")


def _ensure_dirs():
    os.makedirs(os.path.join(_objects_dir(), "blobs"), exist_ok=True)
    os.makedirs(os.path.join(_objects_dir(), "trees"), exist_ok=True)
    os.makedirs(os.path.join(_objects_dir(), "commits"), exist_ok=True)
    os.makedirs(_refs_dir(), exist_ok=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _canonical_dumps(data: Dict) -> str:
    # Stable JSON for hashing
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _write_json_if_absent(path: str, data: Dict) -> None:
    if os.path.exists(path):
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    try:
        os.replace(tmp, path)
    except Exception:
        # Best-effort fallback
        try:
            os.remove(tmp)
        except Exception:
            pass


def _blob_content_from_signature(sig: Dict) -> Dict:
    """Select deterministic content fields from an object signature for the blob.
    Excludes naming and collection placement (tree concern), keeps parent and all state fields.
    """
    # Keys to exclude from blob content (tree or transport concerns)
    exclude = {"name", "collection_path"}
    content = {k: sig[k] for k in sig.keys() if k not in exclude}
    # Ensure a stable shape: add a version and type tag for future migrations
    return {
        "version": 1,
        "type": "object-blob",
        "data": content,
    }


def put_blob_from_signature(sig: Dict) -> Tuple[str, str]:
    """Create a blob from a signature dict. Returns (blob_id, path)."""
    _ensure_dirs()
    payload = _blob_content_from_signature(sig)
    s = _canonical_dumps(payload)
    blob_id = _sha256_text(s)
    path = os.path.join(_objects_dir(), "blobs", f"{blob_id}.json")
    _write_json_if_absent(path, {"kind": "blob", "content": payload})
    return blob_id, path


class _TreeNode:
    __slots__ = ("objects", "children")

    def __init__(self):
        self.objects: Dict[str, str] = {}  # object name -> blob_id
        self.children: Dict[str, "_TreeNode"] = {}  # collection name -> node


def _insert_into_tree(root: _TreeNode, coll_path: str, obj_name: str, blob_id: str) -> None:
    node = root
    parts = [p for p in (coll_path or "").split("|") if p]
    for p in parts:
        node = node.children.setdefault(p, _TreeNode())
    # Within a collection node, names should be unique; last write wins
    node.objects[obj_name] = blob_id


def _flush_tree(node: _TreeNode) -> Tuple[str, Dict]:
    """Write tree recursively. Returns (tree_id, tree_file_content)."""
    # Flush children first to get their IDs
    children_entries = {}
    for name in sorted(node.children.keys()):
        child = node.children[name]
        child_id, _child_payload = _flush_tree(child)
        children_entries[name] = child_id

    # Sort objects by name for determinism
    objects_entries = {k: node.objects[k] for k in sorted(node.objects.keys())}

    content = {
        "version": 1,
        "type": "tree",
        "objects": objects_entries,
        "children": children_entries,
    }
    s = _canonical_dumps(content)
    tree_id = _sha256_text(s)
    path = os.path.join(_objects_dir(), "trees", f"{tree_id}.json")
    _write_json_if_absent(path, {"kind": "tree", "content": content})
    return tree_id, content


def write_tree_from_signatures(obj_sigs: Dict[str, Dict]) -> Tuple[str, Dict[str, str]]:
    """Create blobs and a tree from object signatures.
    Returns (tree_id, name_to_blob_id).
    """
    _ensure_dirs()
    root = _TreeNode()
    mapping: Dict[str, str] = {}
    for nm, sig in obj_sigs.items():
        try:
            blob_id, _ = put_blob_from_signature(sig)
            mapping[nm] = blob_id
            coll_path = sig.get("collection_path", "") or ""
            _insert_into_tree(root, coll_path, nm, blob_id)
        except Exception:
            # Skip any object that fails to serialize
            continue
    tree_id, _ = _flush_tree(root)
    return tree_id, mapping


def read_ref(branch: str) -> Optional[str]:
    try:
        path = os.path.join(_refs_dir(), branch)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                val = f.read().strip()
                return val or None
    except Exception:
        pass
    return None


def update_ref(branch: str, commit_id: str) -> None:
    _ensure_dirs()
    path = os.path.join(_refs_dir(), branch)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(commit_id)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


def write_commit(tree_id: str, uid: str, timestamp: str, message: str, parent: Optional[str] = None) -> str:
    _ensure_dirs()
    content = {
        "version": 1,
        "type": "commit",
        "tree": tree_id,
        "parents": [parent] if parent else [],
        "uid": uid,
        "timestamp": timestamp,
        "message": message,
    }
    s = _canonical_dumps(content)
    commit_id = _sha256_text(s)
    path = os.path.join(_objects_dir(), "commits", f"{commit_id}.json")
    _write_json_if_absent(path, {"kind": "commit", "content": content})
    return commit_id


def create_cas_commit(branch: str, uid: str, timestamp: str, message: str, obj_sigs: Dict[str, Dict]) -> Tuple[str, str]:
    """High-level helper used by the operator: write blobs/trees/commit and update the branch ref.
    Returns (commit_id, tree_id).
    """
    tree_id, _ = write_tree_from_signatures(obj_sigs)
    parent = read_ref(branch)
    commit_id = write_commit(tree_id, uid, timestamp, message, parent)
    update_ref(branch, commit_id)
    return commit_id, tree_id
