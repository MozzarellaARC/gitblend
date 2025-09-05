import os
from typing import Tuple

# Lightweight, optional pygit2 integration for committing .gitblend store
# This module is safe to import even if pygit2 isn't installed.


def _get_store_dir() -> str:
    try:
        from .object_store import get_store_root
        return get_store_root()
    except Exception:
        # Fallback to current working directory if store import fails
        return os.getcwd()


def _default_signature():
    # Resolve author/committer from env or defaults
    name = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("GIT_COMMITTER_NAME") or "Git Blend"
    email = os.environ.get("GIT_AUTHOR_EMAIL") or os.environ.get("GIT_COMMITTER_EMAIL") or "gitblend@example.local"
    return name, email


def try_pygit2_commit(branch: str, message: str, uid: str) -> Tuple[bool, str]:
    """Attempt to commit .gitblend store using pygit2 on the given branch.

    Returns (ok, reason). If pygit2 isn't available or an error occurs, returns (False, reason).
    This function never raises.
    """
    try:
        import pygit2  # type: ignore
    except Exception:
        return False, "pygit2_not_available"

    try:
        repo_dir = _get_store_dir()
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

        # Stage CAS dirs if present
        stage_items = []
        try:
            # Try to include content-addressed store
            for d in ("objects", "refs"):
                p = os.path.join(workdir, d)
                if os.path.exists(p):
                    stage_items.append(d)
        except Exception:
            pass

        try:
            try:
                repo.index.add_all(stage_items)
            except Exception:
                for it in stage_items:
                    try:
                        repo.index.add(it)
                    except Exception:
                        pass
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
