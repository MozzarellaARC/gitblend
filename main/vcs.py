import os
import json
from typing import Tuple, Optional, List, Dict, Any

# Lightweight, optional pygit2 integration for committing .gitblend/index.json
# This module is safe to import even if pygit2 isn't installed.


def _get_index_dir() -> str:
    try:
        from .index import get_index_path
        p = get_index_path()
        return os.path.dirname(p)
    except Exception:
        # Fallback to current working directory if index import fails
        return os.getcwd()


def _get_index_relpath(workdir: str) -> str:
    try:
        from .index import get_index_path
        p = get_index_path()
        return os.path.relpath(p, workdir)
    except Exception:
        return "index.json"


def _default_signature():
    # Resolve author/committer from env or defaults
    name = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("GIT_COMMITTER_NAME") or "Git Blend"
    email = os.environ.get("GIT_AUTHOR_EMAIL") or os.environ.get("GIT_COMMITTER_EMAIL") or "gitblend@example.local"
    return name, email


def try_pygit2_commit(branch: str, message: str, uid: str) -> Tuple[bool, str]:
    """Attempt to commit .gitblend/index.json using pygit2 on the given branch.

    Returns (ok, reason). If pygit2 isn't available or an error occurs, returns (False, reason).
    This function never raises.
    """
    try:
        import pygit2  # type: ignore
    except Exception:
        return False, "pygit2_not_available"

    try:
        repo_dir = _get_index_dir()
        os.makedirs(repo_dir, exist_ok=True)

        repo = None
        # Try opening existing repo
        try:
            repo = pygit2.Repository(repo_dir)
        except Exception:
            repo = None
        # If not a repo, initialize one
        if repo is None:
            try:
                repo = pygit2.init_repository(repo_dir, False)
            except Exception as e:
                return False, f"init_failed:{e}"

        workdir = repo.workdir or repo_dir
        index_rel = _get_index_relpath(workdir)

        # Stage index.json
        try:
            repo.index.add(index_rel)
            repo.index.write()
        except Exception as e:
            return False, f"stage_failed:{e}"

        # Write tree
        try:
            tree_id = repo.index.write_tree()
            tree = repo.get(tree_id)
        except Exception as e:
            return False, f"tree_failed:{e}"

        # Determine parents (current branch tip if it exists)
        refname = f"refs/heads/{branch}"
        parents = []
        try:
            ref = repo.references.get(refname)
            if ref is not None:
                parent = repo.get(ref.target)
                parents = [parent.oid]
        except Exception:
            parents = []

        # Build signature
        aname, aemail = _default_signature()
        try:
            author = committer = pygit2.Signature(aname, aemail)
        except Exception:
            # Fallback to generic hardcoded signature
            author = committer = pygit2.Signature("Git Blend", "gitblend@example.local")

        # Compose message and commit
        full_msg = f"[{branch}] {message}" + (f" ({uid})" if uid else "")
        try:
            commit_id = repo.create_commit(refname, author, committer, full_msg, tree, parents)
        except Exception as e:
            return False, f"commit_failed:{e}"

        # Optionally create a lightweight tag for the UID
        if uid:
            try:
                safe_tag = f"gitblend-{branch}-{uid}"
                tag_ref = f"refs/tags/{safe_tag}"
                if repo.references.get(tag_ref) is None:
                    repo.create_reference(tag_ref, commit_id)
            except Exception:
                # Non-fatal if tag creation fails
                pass

        # Point HEAD to the branch (helpful for future ops)
        try:
            repo.set_head(refname)
        except Exception:
            pass

        return True, "ok"
    except Exception as e:
        return False, f"unexpected:{e}"


# ----------------------------
# Pygit2-exclusive VCS helpers
# ----------------------------

def _repo() -> Optional[object]:
    try:
        import pygit2  # type: ignore
    except Exception:
        return None
    d = _get_index_dir()
    os.makedirs(d, exist_ok=True)
    try:
        return pygit2.Repository(d)
    except Exception:
        try:
            return pygit2.init_repository(d, False)
        except Exception:
            return None


def commit_snapshot(branch: str, uid: str, timestamp: str, message: str,
                    snapshot_name: str, obj_sigs: Dict[str, Dict[str, Any]], collection_hash: str) -> Tuple[bool, str]:
    """Write a commit that stores snapshot metadata into index.json and commits via pygit2.
    The JSON format is per-commit (no overall branches dict), using keys: uid, timestamp, message, snapshot, collection_hash, objects(list).
    """
    try:
        import pygit2  # type: ignore
    except Exception:
        return False, "pygit2_not_available"

    repo = _repo()
    if repo is None:
        return False, "repo_not_available"

    workdir = repo.workdir or _get_index_dir()
    idx_path = os.path.join(workdir, "index.json")

    # Build per-commit JSON payload
    commit_obj_list = [obj_sigs[nm] for nm in sorted(obj_sigs.keys())]
    data = {
        "uid": uid,
        "timestamp": timestamp,
        "message": message,
        "snapshot": snapshot_name,
        "collection_hash": collection_hash,
        "objects": commit_obj_list,
        "branch": branch,
    }

    # Write file
    try:
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return False, f"write_failed:{e}"

    # Stage and commit
    try:
        rel = os.path.relpath(idx_path, workdir)
        repo.index.add(rel)
        repo.index.write()
        tree_id = repo.index.write_tree()
        refname = f"refs/heads/{branch}"
        parents = []
        try:
            ref = repo.references.get(refname)
            if ref is not None:
                parents = [ref.target]
        except Exception:
            parents = []
        author_name, author_email = _default_signature()
        sig = pygit2.Signature(author_name, author_email)
        full_msg = f"[{branch}] {message} ({uid})"
        commit_id = repo.create_commit(refname, sig, sig, full_msg, tree_id, parents)
        try:
            repo.set_head(refname)
        except Exception:
            pass
        return True, str(commit_id)
    except Exception as e:
        return False, f"commit_failed:{e}"


def read_head_commit(branch: str) -> Optional[Dict[str, Any]]:
    """Return JSON dict from HEAD:index.json for branch, or None if missing."""
    repo = _repo()
    if repo is None:
        return None
    refname = f"refs/heads/{branch}"
    try:
        ref = repo.references.get(refname)
        if ref is None:
            return None
        head_commit = repo.get(ref.target)
        tree = head_commit.tree
        # Look up index.json blob
        try:
            entry = tree["index.json"]
        except KeyError:
            return None
        blob = repo.get(entry.oid)
        try:
            return json.loads(blob.data.decode("utf-8"))
        except Exception:
            return None
    except Exception:
        return None


def list_commits(branch: str, max_count: int = 100) -> List[Dict[str, Any]]:
    """List recent commits on branch by reading index.json from each; newest first."""
    repo = _repo()
    if repo is None:
        return []
    refname = f"refs/heads/{branch}"
    out: List[Dict[str, Any]] = []
    try:
        ref = repo.references.get(refname)
        if ref is None:
            return []
        oid = ref.target
        count = 0
        while oid and count < max_count:
            commit = repo.get(oid)
            tree = commit.tree
            try:
                entry = tree["index.json"]
                blob = repo.get(entry.oid)
                data = json.loads(blob.data.decode("utf-8"))
                # attach uid fallback if missing
                if not isinstance(data, dict):
                    data = {}
                if "uid" not in data or not data.get("uid"):
                    data["uid"] = str(commit.id)
                out.append(data)
            except Exception:
                # skip commits without index.json
                pass
            # Move to first parent
            if len(commit.parent_ids) == 0:
                break
            oid = commit.parent_ids[0]
            count += 1
    except Exception:
        return out
    return out


def find_commit_by_uid(branch: str, uid: str) -> Optional[Dict[str, Any]]:
    for c in list_commits(branch, max_count=1000):
        try:
            if str(c.get("uid", "")) == str(uid):
                return c
        except Exception:
            continue
    return None


def reset_branch_to_parent(branch: str) -> Tuple[bool, str]:
    """Move branch head to its first parent (undo last commit)."""
    repo = _repo()
    if repo is None:
        return False, "repo_not_available"
    refname = f"refs/heads/{branch}"
    try:
        ref = repo.references.get(refname)
        if ref is None:
            return False, "no_ref"
        commit = repo.get(ref.target)
        if len(commit.parent_ids) == 0:
            # Detach to empty (delete branch)
            repo.references.delete(refname)
            return True, "deleted_branch"
        parent_oid = commit.parent_ids[0]
        repo.references.set(refname, parent_oid)
        try:
            repo.set_head(refname)
        except Exception:
            pass
        return True, "ok"
    except Exception as e:
        return False, f"reset_failed:{e}"
