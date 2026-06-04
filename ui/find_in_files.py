"""Find in Files — project-wide text search with results grouped by file."""
from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QToolButton, QTreeWidget,
    QTreeWidgetItem, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal

_IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build",
    ".idea", ".vs", "bin", "obj", "target",
}
_TEXT_EXT = {
    ".py", ".pyw", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".cs", ".js",
    ".ts", ".jsx", ".tsx", ".json", ".md", ".txt", ".html", ".css", ".java",
    ".go", ".rs", ".rb", ".php", ".lua", ".sh", ".yml", ".yaml", ".toml",
    ".ini", ".cfg", ".xml", ".kt", ".swift", ".dart", ".vue", ".sql",
}
_MAX_FILES = 5000
_MAX_HITS = 1000


class FindInFiles(QWidget):
    result_activated = pyqtSignal(str, int, int)  # (path, line, col)

    def __init__(self):
        super().__init__()
        self.root: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search across project…")
        self.input.returnPressed.connect(self.search)
        self.btn_case = self._toggle("Aa", "Match case")
        self.btn_regex = self._toggle(".*", "Regex")
        row.addWidget(self.input, 1)
        row.addWidget(self.btn_case)
        row.addWidget(self.btn_regex)
        layout.addLayout(row)

        self.summary = QLabel("")
        self.summary.setStyleSheet("color: #6c7086;")
        layout.addWidget(self.summary)

        self.results = QTreeWidget()
        self.results.setHeaderHidden(True)
        self.results.itemActivated.connect(self._on_activate)
        self.results.itemClicked.connect(self._on_activate)
        layout.addWidget(self.results, 1)

    def _toggle(self, text: str, tip: str) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(True)
        return b

    def set_root(self, root: str) -> None:
        self.root = root

    def focus(self) -> None:
        self.input.setFocus()
        self.input.selectAll()

    # ------------------------------------------------------------ search
    def search(self) -> None:
        self.results.clear()
        query = self.input.text()
        if not query or not self.root:
            self.summary.setText("Open a folder and type a query")
            return
        try:
            pattern = re.compile(
                query if self.btn_regex.isChecked() else re.escape(query),
                0 if self.btn_case.isChecked() else re.IGNORECASE,
            )
        except re.error as exc:
            self.summary.setText(f"Bad regex: {exc}")
            return

        files_scanned = 0
        total_hits = 0
        file_count = 0
        root_path = Path(self.root)
        for path in root_path.rglob("*"):
            if files_scanned >= _MAX_FILES or total_hits >= _MAX_HITS:
                break
            if not path.is_file() or path.suffix.lower() not in _TEXT_EXT:
                continue
            if any(part in _IGNORE_DIRS for part in path.parts):
                continue
            files_scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            hits = []
            for i, line in enumerate(text.splitlines()):
                m = pattern.search(line)
                if m:
                    hits.append((i, m.start(), line.strip()[:200]))
                    total_hits += 1
                    if total_hits >= _MAX_HITS:
                        break
            if hits:
                file_count += 1
                self._add_file(root_path, path, hits)

        self.summary.setText(
            f"{total_hits} results in {file_count} files "
            f"({files_scanned} scanned)"
        )
        self.results.expandAll()

    def _add_file(self, root: Path, path: Path, hits) -> None:
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = path.name
        parent = QTreeWidgetItem([f"{rel}  ({len(hits)})"])
        parent.setData(0, Qt.ItemDataRole.UserRole, None)
        self.results.addTopLevelItem(parent)
        for line, col, preview in hits:
            child = QTreeWidgetItem([f"  {line + 1}: {preview}"])
            child.setData(0, Qt.ItemDataRole.UserRole, (str(path), line, col))
            parent.addChild(child)

    def _on_activate(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            path, line, col = data
            self.result_activated.emit(path, line, col)
