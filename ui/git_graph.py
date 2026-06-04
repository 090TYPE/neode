"""Git graph — recent commit history from the open repository (pygit2)."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt

try:
    import pygit2  # type: ignore
    HAVE_PYGIT2 = True
except Exception:  # pragma: no cover
    pygit2 = None
    HAVE_PYGIT2 = False

_MAX_COMMITS = 300


class GitGraph(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("Git Graph")
        tf = title.font(); tf.setPointSize(tf.pointSize() + 6); tf.setBold(True)
        title.setFont(tf)
        head.addWidget(title)
        head.addStretch(1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        head.addWidget(refresh)
        layout.addLayout(head)

        self.info = QLabel("")
        self.info.setStyleSheet("color: #6c7086;")
        layout.addWidget(self.info)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Graph", "Commit", "Author", "When"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 60)
        self.tree.setColumnWidth(1, 460)
        self.tree.setColumnWidth(2, 140)
        layout.addWidget(self.tree, 1)

        self.refresh()

    def _repo(self):
        return getattr(self.window.file_tree.git, "repo", None)

    def refresh(self) -> None:
        self.tree.clear()
        if not HAVE_PYGIT2:
            self.info.setText("pygit2 is not available.")
            return
        repo = self._repo()
        if repo is None:
            self.info.setText("Open a folder that is a git repository.")
            return
        try:
            branch = repo.head.shorthand
        except Exception:
            self.info.setText("Repository has no commits yet.")
            return

        # branch tip oids -> label, to mark refs
        refs: dict[str, list[str]] = {}
        try:
            for name in repo.references:
                ref = repo.references[name]
                try:
                    oid = str(ref.peel().id)
                    refs.setdefault(oid, []).append(name.split("/")[-1])
                except Exception:
                    pass
        except Exception:
            pass

        count = 0
        try:
            walker = repo.walk(repo.head.target,
                               pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME)
            for commit in walker:
                if count >= _MAX_COMMITS:
                    break
                oid = str(commit.id)
                summary = commit.message.splitlines()[0] if commit.message else ""
                tags = refs.get(oid, [])
                label = ("● " + "  ".join(f"[{t}]" for t in tags) + " " if tags
                         else "●")
                when = datetime.fromtimestamp(commit.commit_time).strftime(
                    "%Y-%m-%d %H:%M")
                item = QTreeWidgetItem([
                    label, f"{oid[:7]}  {summary}", commit.author.name, when])
                if tags:
                    item.setForeground(1, QColor("#a6e3a1"))
                self.tree.addTopLevelItem(item)
                count += 1
        except Exception as exc:
            self.info.setText(f"Could not read history: {exc}")
            return
        self.info.setText(f"Branch {branch} · {count} commits")
