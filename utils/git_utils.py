from __future__ import annotations

import os
import shutil
import subprocess
from typing import Iterable, List


# Explicit paths per structure.prompt.md, with PATH fallback
GIT_EXE_HINT = r"C:\\Program Files\\Git\\bin\\git.exe"
GIT_LFS_EXE_HINT = r"C:\\Program Files\\Git LFS\\git-lfs.exe"


class GitError(RuntimeError):
    pass


def _resolve_git_path() -> str | None:
    if os.path.exists(GIT_EXE_HINT):
        return GIT_EXE_HINT
    return shutil.which("git")


def _resolve_lfs_path() -> str | None:
    if os.path.exists(GIT_LFS_EXE_HINT):
        return GIT_LFS_EXE_HINT
    # Fallback to PATH
    return shutil.which("git-lfs") or shutil.which("git-lfs.exe")


def _run_exec(exec_path: str, args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [exec_path, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    git = _resolve_git_path()
    if not git:
        raise GitError("git executable not found. Expected at 'C:/Program Files/Git/bin/git.exe' or on PATH")
    return _run_exec(git, args, cwd)


def _run_lfs(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    lfs = _resolve_lfs_path()
    if not lfs:
        raise GitError("git-lfs executable not found. Expected at 'C:/Program Files/Git LFS/git-lfs.exe' or on PATH")
    return _run_exec(lfs, args, cwd)


def git_available() -> bool:
    return _resolve_git_path() is not None


def lfs_available() -> bool:
    return _resolve_lfs_path() is not None


def ensure_repo(repo_dir: str) -> None:
    if not os.path.isdir(repo_dir):
        os.makedirs(repo_dir, exist_ok=True)

    if not git_available():
        raise GitError("git is not available at the expected path or on PATH")

    git_dir = os.path.join(repo_dir, ".git")
    if not os.path.isdir(git_dir):
        p = _run_git(["init"], cwd=repo_dir)
        if p.returncode != 0:
            raise GitError(p.stderr or p.stdout)

    # Always ensure LFS and attributes for .blend
    ensure_lfs(repo_dir)


def ensure_lfs(repo_dir: str, patterns: Iterable[str] | None = None) -> None:
    patterns = list(patterns or ["*.blend"])  # default track .blend files

    if not lfs_available():
        # Still usable without LFS, but we track only if available
        return

    # Install LFS scoped to this repo
    p = _run_lfs(["install", "--local"], cwd=repo_dir)
    if p.returncode != 0:
        raise GitError(p.stderr or p.stdout)

    for pat in patterns:
        p = _run_lfs(["track", pat], cwd=repo_dir)
        if p.returncode != 0:
            raise GitError(p.stderr or p.stdout)

    # Stage .gitattributes if created/changed
    attrs_path = os.path.join(repo_dir, ".gitattributes")
    if os.path.exists(attrs_path):
        p = _run_git(["add", ".gitattributes"], cwd=repo_dir)
        if p.returncode != 0:
            raise GitError(p.stderr or p.stdout)

        # Commit silently if there are staged changes
        _run_git(["commit", "-m", "chore(git-blend): ensure LFS tracking"], cwd=repo_dir)


def add_and_commit(repo_dir: str, paths: Iterable[str], message: str) -> None:
    rel_paths: List[str] = []
    for pth in paths:
        rel_paths.append(os.path.normpath(pth))

    p = _run_git(["add", *rel_paths], cwd=repo_dir)
    if p.returncode != 0:
        raise GitError(p.stderr or p.stdout)

    p = _run_git(["commit", "-m", message], cwd=repo_dir)
    if p.returncode != 0:
        # No changes to commit isn't fatal
        combined = (p.stderr or "") + "\n" + (p.stdout or "")
        if "nothing to commit" not in combined.lower():
            raise GitError(p.stderr or p.stdout)


def ensure_ignore(repo_dir: str, lines: Iterable[str]) -> None:
    gi_path = os.path.join(repo_dir, ".gitignore")
    existing: set[str] = set()
    if os.path.exists(gi_path):
        with open(gi_path, "r", encoding="utf-8") as f:
            existing = {ln.strip() for ln in f.readlines()}
    desired = list(lines)
    updated = False
    with open(gi_path, "a", encoding="utf-8") as f:
        for ln in desired:
            if ln not in existing:
                f.write(ln + "\n")
                updated = True
    if updated:
        _run_git(["add", ".gitignore"], cwd=repo_dir)
        _run_git(["commit", "-m", "chore(git-blend): update .gitignore"], cwd=repo_dir)
