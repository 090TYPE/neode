"""Per-line git change status and blame, computed from a pygit2 repo.

Used by the editor's git gutter (added/modified/deleted markers) and the
status-bar inline blame. All functions degrade to empty results when pygit2 or
a repository is unavailable.
"""
from __future__ import annotations

import difflib
from datetime import datetime, timezone
from pathlib import Path

try:
    import pygit2  # type: ignore
    HAVE_PYGIT2 = True
except Exception:  # pragma: no cover
    pygit2 = None
    HAVE_PYGIT2 = False

_MAX_BLAME_LINES = 4000


def _rel(repo, abs_path: str) -> str | None:
    try:
        workdir = Path(repo.workdir)
        return str(Path(abs_path).resolve().relative_to(workdir)).replace("\\", "/")
    except Exception:
        return None


def _head_text(repo, rel: str) -> str | None:
    """Return the file's content at HEAD, or None if it isn't tracked."""
    try:
        head = repo.revparse_single("HEAD")
        tree = head.tree
        entry = tree[rel]            # KeyError if not present
        blob = repo[entry.id]
        return blob.data.decode("utf-8", errors="replace")
    except Exception:
        return None


def line_status(repo, abs_path: str, current_text: str) -> dict[int, str]:
    """Map 0-based line -> 'added' | 'modified' | 'deleted' (vs HEAD)."""
    if repo is None or not HAVE_PYGIT2:
        return {}
    rel = _rel(repo, abs_path)
    if rel is None:
        return {}
    old = _head_text(repo, rel)
    if old is None:
        # untracked / new file: everything is added
        return {i: "added" for i in range(len(current_text.splitlines()))}

    old_lines = old.splitlines()
    new_lines = current_text.splitlines()
    status: dict[int, str] = {}
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            for j in range(j1, j2):
                status[j] = "modified"
        elif tag == "insert":
            for j in range(j1, j2):
                status[j] = "added"
        elif tag == "delete":
            # deletion happens *between* new lines; flag the line at j1
            status[max(j1 - 1, 0)] = "deleted"
    return status


def blame_lines(repo, abs_path: str) -> dict[int, tuple[str, str, str]]:
    """Map 0-based line -> (author, when, summary). Empty for big/untracked files."""
    if repo is None or not HAVE_PYGIT2:
        return {}
    rel = _rel(repo, abs_path)
    if rel is None:
        return {}
    try:
        blame = repo.blame(rel)
    except Exception:
        return {}
    out: dict[int, tuple[str, str, str]] = {}
    try:
        for hunk in blame:
            commit = repo[hunk.final_commit_id]
            author = commit.author.name
            when = _ago(commit.commit_time)
            summary = commit.message.splitlines()[0] if commit.message else ""
            start = hunk.final_start_line_number - 1
            for n in range(hunk.lines_in_hunk):
                line = start + n
                if line > _MAX_BLAME_LINES:
                    return out
                out[line] = (author, when, summary)
    except Exception:
        return out
    return out


def _ago(commit_time: int) -> str:
    try:
        then = datetime.fromtimestamp(commit_time, tz=timezone.utc)
        delta = datetime.now(tz=timezone.utc) - then
        secs = int(delta.total_seconds())
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60} min ago"
        if secs < 86400:
            return f"{secs // 3600} h ago"
        days = secs // 86400
        if days < 30:
            return f"{days} d ago"
        if days < 365:
            return f"{days // 30} mo ago"
        return f"{days // 365} y ago"
    except Exception:
        return ""
