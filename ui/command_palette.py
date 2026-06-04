"""Command Palette (Ctrl+Shift+P) — fuzzy search over registered commands."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QWidget, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt


@dataclass
class Command:
    title: str
    shortcut: str | None
    callback: object


class CommandPalette(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.resize(560, 380)
        self.commands: list[Command] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command…")
        self.search.textChanged.connect(self._filter)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _i: self._run_selected())
        layout.addWidget(self.list)

    # ------------------------------------------------------------ registration
    def register(self, title: str, shortcut: str | None, callback) -> None:
        self.commands.append(Command(title, shortcut, callback))

    # ------------------------------------------------------------ show & filter
    def popup(self) -> None:
        self.search.clear()
        self._filter("")
        if self.parent():
            geo = self.parent().geometry()
            self.move(geo.center().x() - self.width() // 2, geo.top() + 80)
        self.search.setFocus()
        self.show()

    def _score(self, query: str, title: str) -> float:
        q, t = query.lower(), title.lower()
        if not q:
            return 1.0
        if q in t:
            return 1.0 + (1.0 - t.index(q) / max(len(t), 1))
        return SequenceMatcher(None, q, t).ratio()

    def _filter(self, query: str) -> None:
        self.list.clear()
        scored = [
            (self._score(query, c.title), c) for c in self.commands
        ]
        scored = [sc for sc in scored if not query or sc[0] > 0.3]
        scored.sort(key=lambda sc: sc[0], reverse=True)
        for _score, cmd in scored:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self.list.addItem(item)
            self.list.setItemWidget(item, self._row(cmd))
        if self.list.count():
            self.list.setCurrentRow(0)

    def _row(self, cmd: Command) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(10, 6, 10, 6)
        h.addWidget(QLabel(cmd.title))
        h.addStretch(1)
        if cmd.shortcut:
            sc = QLabel(cmd.shortcut)
            sc.setStyleSheet("color: #6c7086;")
            h.addWidget(sc)
        return w

    # ------------------------------------------------------------ keyboard nav
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
                self._run_selected()
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)

    def _run_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        cmd: Command = item.data(Qt.ItemDataRole.UserRole)
        self.close()
        if callable(cmd.callback):
            cmd.callback()
