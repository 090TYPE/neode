"""Thin pygit2 wrapper. Degrades gracefully when pygit2 or a repo is absent."""
from __future__ import annotations

from pathlib import Path

try:
    import pygit2  # type: ignore
    HAVE_PYGIT2 = True
except Exception:  # pragma: no cover - optional dependency
    pygit2 = None
    HAVE_PYGIT2 = False


class GitStatus:
    def __init__(self):
        self.repo = None
        self._status: dict[str, str] = {}

    def open(self, folder: str) -> None:
        self.repo = None
        self._status = {}
        if not HAVE_PYGIT2:
            return
        try:
            git_dir = pygit2.discover_repository(folder)
            if git_dir:
                self.repo = pygit2.Repository(git_dir)
        except Exception:
            self.repo = None

    @property
    def branch(self) -> str:
        if self.repo is None:
            return ""
        try:
            return self.repo.head.shorthand
        except Exception:
            return "(detached)"

    def refresh(self) -> None:
        self._status = {}
        if self.repo is None:
            return
        try:
            workdir = Path(self.repo.workdir)
        except Exception:
            return
        try:
            for rel, flags in self.repo.status().items():
                full = str((workdir / rel).resolve())
                self._status[full] = self._classify(flags)
        except Exception:
            pass

    def _classify(self, flags: int) -> str:
        if not HAVE_PYGIT2:
            return ""
        new = pygit2.GIT_STATUS_WT_NEW | pygit2.GIT_STATUS_INDEX_NEW
        mod = pygit2.GIT_STATUS_WT_MODIFIED | pygit2.GIT_STATUS_INDEX_MODIFIED
        deleted = pygit2.GIT_STATUS_WT_DELETED | pygit2.GIT_STATUS_INDEX_DELETED
        if flags & deleted:
            return "deleted"
        if flags & mod:
            return "modified"
        if flags & new:
            return "new"
        return ""

    def status_for(self, path: str) -> str:
        return self._status.get(str(Path(path).resolve()), "")

    # ------------------------------------------------------------ staging/commit
    def changed_files(self) -> list[tuple[str, str]]:
        """Return (relative_path, status) for every changed file."""
        if self.repo is None:
            return []
        out = []
        try:
            for rel, flags in self.repo.status().items():
                out.append((rel, self._classify(flags)))
        except Exception:
            pass
        return sorted(out)

    def stage_all(self) -> bool:
        if self.repo is None:
            return False
        try:
            index = self.repo.index
            index.add_all()
            index.write()
            return True
        except Exception:
            return False

    def commit(self, message: str) -> str:
        """Stage everything and commit. Returns a human-readable result."""
        if self.repo is None:
            return "No git repository"
        if not message.strip():
            return "Empty commit message"
        try:
            index = self.repo.index
            index.add_all()
            index.write()
            tree = index.write_tree()
            try:
                sig = self.repo.default_signature
            except Exception:
                sig = pygit2.Signature("NeoIDE", "neoide@localhost")
            parents = [] if self.repo.head_is_unborn else [self.repo.head.target]
            ref = "HEAD"
            self.repo.create_commit(ref, sig, sig, message, tree, parents)
            self.refresh()
            return "Committed"
        except Exception as exc:
            return f"Commit failed: {exc}"
