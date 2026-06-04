"""Breadcrumbs bar — file path segments + the symbol at the cursor.

Sits above the editor tabs. Clicking the symbol crumb jumps to its definition.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from ui.symbols_panel import extract_symbols


class _Crumb(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str, clickable: bool = False):
        super().__init__(text)
        self.setObjectName("Crumb")
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clickable = clickable

    def mousePressEvent(self, event):  # noqa: N802
        if self._clickable:
            self.clicked.emit()


class Breadcrumbs(QWidget):
    symbol_clicked = pyqtSignal(int)   # line to jump to

    def __init__(self):
        super().__init__()
        self.setObjectName("Breadcrumbs")
        self.setFixedHeight(26)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 0, 10, 0)
        self._layout.setSpacing(4)
        self._root: str | None = None
        self.hide()

    def set_root(self, root: str | None) -> None:
        self._root = root

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def update_for(self, path: str | None, text: str, language: str,
                   cursor_line: int) -> None:
        self._clear()
        if not path:
            self.hide()
            return
        # path segments
        p = Path(path)
        try:
            rel = p.relative_to(self._root) if self._root else p
            parts = list(rel.parts)
        except ValueError:
            parts = [p.name]
        for i, part in enumerate(parts):
            self._layout.addWidget(_Crumb(part))
            if i < len(parts) - 1:
                self._layout.addWidget(_Crumb("›"))

        # enclosing symbol at the cursor
        symbol = self._enclosing_symbol(text, language, cursor_line)
        if symbol is not None:
            line, name = symbol
            self._layout.addWidget(_Crumb("›"))
            crumb = _Crumb(name, clickable=True)
            crumb.clicked.connect(lambda ln=line: self.symbol_clicked.emit(ln))
            self._layout.addWidget(crumb)

        self._layout.addStretch(1)
        self.show()

    @staticmethod
    def _enclosing_symbol(text: str, language: str, cursor_line: int):
        syms = extract_symbols(text, language)
        if not syms:
            return None
        chosen = None
        min_indent = 1 << 30
        for line, indent, txt in reversed(syms):
            if line <= cursor_line and indent < min_indent:
                # short display: drop trailing ':' / '{'
                name = txt.rstrip("{ :").split("(")[0]
                name = name.replace("def ", "").replace("class ", "").strip()
                chosen = (line, name.split()[-1] if name.split() else name)
                min_indent = indent
                if indent == 0:
                    break
        return chosen
