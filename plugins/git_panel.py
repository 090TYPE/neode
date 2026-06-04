"""Built-in plugin: Git panel — changed files + commit box.

Adds a "Git" tab to the side panel listing modified/new/deleted files with a
message box and a Commit button (stages everything, then commits via pygit2).
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPlainTextEdit,
    QPushButton, QLabel, QHBoxLayout
)
from PyQt6.QtGui import QColor

from plugins.base import BasePlugin

_COLORS = {"modified": "#f9e2af", "new": "#a6e3a1", "deleted": "#f38ba8"}


class Plugin(BasePlugin):
    name = "Git Panel"
    version = "1.0.0"

    def activate(self) -> None:
        self.panel = QWidget()
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(6, 6, 6, 6)

        self.header = QLabel("Changes")
        self.header.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.header)

        self.files = QListWidget()
        self.files.itemDoubleClicked.connect(self._open_file)
        layout.addWidget(self.files, 1)

        self.message = QPlainTextEdit()
        self.message.setPlaceholderText("Commit message…")
        self.message.setFixedHeight(64)
        layout.addWidget(self.message)

        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        commit = QPushButton("Commit")
        commit.clicked.connect(self._commit)
        row.addWidget(refresh)
        row.addWidget(commit)
        layout.addLayout(row)

        self.api.ui.add_panel("Git", self.panel)
        self.api.ui.register_command("Git: Refresh Changes", self.refresh)
        self.api.ui.register_command("Git: Commit", self._commit)
        # auto-refresh after every save
        self.api.events.on("file_saved", lambda *_a: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        self.files.clear()
        git = self.api.git.status
        git.refresh()
        branch = git.branch or "(no repo)"
        changes = git.changed_files()
        self.header.setText(f"Changes on {branch} — {len(changes)}")
        for rel, status in changes:
            item = QListWidgetItem(f"{status[:1].upper()}  {rel}")
            item.setData(0x0100, rel)  # Qt.UserRole
            color = _COLORS.get(status)
            if color:
                item.setForeground(QColor(color))
            self.files.addItem(item)

    def _open_file(self, item: QListWidgetItem) -> None:
        rel = item.data(0x0100)
        git = self.api.git.status
        if git.repo is not None and rel:
            from pathlib import Path
            full = str(Path(git.repo.workdir) / rel)
            self.api.ui.open_file(full)

    def _commit(self) -> None:
        msg = self.message.toPlainText().strip()
        if not msg:
            self.api.ui.show_notification("Enter a commit message first", 2500)
            return
        result = self.api.git.status.commit(msg)
        self.api.ui.show_notification(f"Git: {result}", 3000)
        if result == "Committed":
            self.message.clear()
        self.refresh()
        self.api.git.refresh()
