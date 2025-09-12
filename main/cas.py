import os
import json
import hashlib
from typing import Dict, Tuple, Optional, List
from ..prefs.properties import SCENE_DIR, HIDDEN_SCENE_DIR

# Pretty JSON on disk for readability. Hashing still uses compact canonical form.
PRETTY_JSON_INDENT = 2


def _project_root_dir() -> str:
    # Avoid importing bpy here; rely on caller paths. Fallback to CWD.
    try:
        import bpy  # type: ignore
        root = bpy.path.abspath("//") or os.getcwd()
        return root
    except Exception:
        return os.getcwd()


def _store_root() -> str:
    return os.path.join(_project_root_dir(), HIDDEN_SCENE_DIR)


def _objects_dir() -> str:
    return os.path.join(_store_root(), "objects")


def _refs_dir() -> str:
    return os.path.join(_store_root(), "refs", "heads")


def get_store_root() -> str:
    """Public helper to retrieve the .gitblend store root folder."""
    return _store_root()


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
    """Write JSON file only if it doesn't already exist.

    Stored JSON is pretty-printed for human readability while maintaining
    deterministic key ordering. Object IDs are derived from the canonical
    compact representation (see _canonical_dumps) before this is called,
    so adding indentation here is safe and doesn't affect hashes.
    """
    if os.path.exists(path):
        return
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                sort_keys=True,
                indent=PRETTY_JSON_INDENT,
            )
            f.write("\n")  # ensure trailing newline for POSIX tools
        os.replace(tmp, path)
    except Exception:
        # Best-effort cleanup if something failed after creating tmp
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


# ===================== Reading / Query helpers =====================

def _objects_paths(kind: str, oid: str) -> str:
    return os.path.join(_objects_dir(), kind, f"{oid}.json")


def _read_json(path: str) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def read_commit(commit_id: str) -> Optional[Dict]:
    p = _objects_paths("commits", commit_id)
    data = _read_json(p)
    if not data:
        return None
    return data.get("content") or data


def read_tree(tree_id: str) -> Optional[Dict]:
    p = _objects_paths("trees", tree_id)
    data = _read_json(p)
    if not data:
        return None
    return data.get("content") or data


def read_blob(blob_id: str) -> Optional[Dict]:
    p = _objects_paths("blobs", blob_id)
    data = _read_json(p)
    if not data:
        return None
    return data.get("content") or data


def flatten_tree_to_objects(tree_id: str) -> Dict[str, Dict]:
    """Return name->signature-like dicts reconstructed from the tree and blobs.
    Adds 'name' and 'collection_path' so consumers can compare with current signatures.
    """
    def walk(node_id: str, path_parts: List[str], out: Dict[str, Dict]):
        node = read_tree(node_id)
        if not node:
            return
        objects = node.get("objects", {}) or {}
        for nm, bid in objects.items():
            b = read_blob(bid)
            if not b:
                continue
            data = dict(b.get("data", {}))
            data["name"] = nm
            data["collection_path"] = "|".join(path_parts)
            out[nm] = data
        children = node.get("children", {}) or {}
        for cname in sorted(children.keys()):
            walk(children[cname], path_parts + [cname], out)

    out: Dict[str, Dict] = {}
    walk(tree_id, [], out)
    return out


def get_branch_head_commit(branch: str) -> Optional[Tuple[str, Dict]]:
    """Return (commit_id, commit_content) for branch head, if any."""
    cid = read_ref(branch)
    if not cid:
        return None
    c = read_commit(cid)
    if not c:
        return None
    return cid, c


def get_latest_commit_objects(branch: str) -> Optional[Tuple[str, Dict, Dict[str, Dict]]]:
    """Return (commit_id, commit_content, objs_map) for branch head."""
    head = get_branch_head_commit(branch)
    if not head:
        return None
    cid, commit = head
    tree_id = commit.get("tree")
    if not tree_id:
        return None
    objs = flatten_tree_to_objects(tree_id)
    return cid, commit, objs


def resolve_commit_by_uid(branch: str, uid: str) -> Optional[Tuple[str, Dict]]:
    """Walk parents from branch head to find a commit with matching uid. Returns (id, content)."""
    seen: set[str] = set()
    cur = read_ref(branch)
    while cur and cur not in seen:
        seen.add(cur)
        c = read_commit(cur)
        if not c:
            break
        if str(c.get("uid", "")) == str(uid):
            return cur, c
        parents = c.get("parents", []) or []
        cur = parents[0] if parents else None
    return None


def list_branch_commits(branch: str, limit: int = 1000) -> List[Tuple[str, Dict]]:
    """Return a linear list from head back to root (first parent), up to 'limit'."""
    res: List[Tuple[str, Dict]] = []
    seen: set[str] = set()
    cur = read_ref(branch)
    while cur and cur not in seen and len(res) < limit:
        seen.add(cur)
        c = read_commit(cur)
        if not c:
            break
        res.append((cur, c))
        parents = c.get("parents", []) or []
        cur = parents[0] if parents else None
    return res

