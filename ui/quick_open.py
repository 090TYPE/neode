"""Quick Open (Ctrl+P) — fuzzy filename search across the project folder."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal

# directories we never want to index
_IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build",
    ".idea", ".vs", "bin", "obj", "target",
}
_MAX_FILES = 6000


class QuickOpen(QDialog):
    file_chosen = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.resize(620, 420)
        self._files: list[tuple[str, str]] = []  # (relative, absolute)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Go to file…")
        self.search.textChanged.connect(self._filter)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _i: self._choose())
        layout.addWidget(self.list)

    # ------------------------------------------------------------ indexing
    def index(self, root: str) -> None:
        self._files = []
        root_path = Path(root)
        count = 0
        for path in root_path.rglob("*"):
            if count >= _MAX_FILES:
                break
            if not path.is_file():
                continue
            if any(part in _IGNORE_DIRS for part in path.parts):
                continue
            try:
                rel = str(path.relative_to(root_path))
            except ValueError:
                rel = path.name
            self._files.append((rel.replace("\\", "/"), str(path)))
            count += 1
        self._files.sort(key=lambda t: t[0].lower())

    # ------------------------------------------------------------ show/filter
    def popup(self) -> None:
        self.search.clear()
        self._filter("")
        if self.parent():
            geo = self.parent().geometry()
            self.move(geo.center().x() - self.width() // 2, geo.top() + 80)
        self.search.setFocus()
        self.show()

    @staticmethod
    def _subseq_score(query: str, target: str) -> int | None:
        """Return a score if every query char appears in order; lower is better."""
        if not query:
            return 0
        q = query.lower()
        t = target.lower()
        ti = 0
        last = -1
        gaps = 0
        for ch in q:
            idx = t.find(ch, ti)
            if idx == -1:
                return None
            if last >= 0:
                gaps += idx - last - 1
            last = idx
            ti = idx + 1
        # prefer matches in the basename and with fewer gaps
        base_bonus = 0 if "/" in t[t.rfind(q[0]):] else -20
        return gaps + base_bonus

    def _filter(self, query: str) -> None:
        self.list.clear()
        scored = []
        for rel, absolute in self._files:
            score = self._subseq_score(query, rel)
            if score is not None:
                scored.append((score, rel, absolute))
        scored.sort(key=lambda s: (s[0], len(s[1])))
        for _score, rel, absolute in scored[:200]:
            item = QListWidgetItem(rel)
            item.setData(Qt.ItemDataRole.UserRole, absolute)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    # ------------------------------------------------------------ keyboard
    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.search and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self.list.setCurrentRow(
                    min(self.list.currentRow() + 1, self.list.count() - 1))
                return True
            if key == Qt.Key.Key_Up:
                self.list.setCurrentRow(max(self.list.currentRow() - 1, 0))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._choose()
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)

    def _choose(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        self.close()
        self.file_chosen.emit(path)
