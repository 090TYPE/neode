"""Symbols outline — lists classes / functions in the current file.

Uses lightweight per-language regexes (no LSP round-trip needed) so the outline
appears instantly. Clicking an entry jumps the editor to that line.
"""
from __future__ import annotations

import re

from PyQt6.QtWidgets import QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal

# language -> list of (kind, compiled regex with a 'name' group)
_PATTERNS = {
    "Python": [
        ("class", re.compile(r"^\s*class\s+(?P<name>\w+)")),
        ("def", re.compile(r"^\s*def\s+(?P<name>\w+)")),
    ],
    "C++": [
        ("class", re.compile(r"^\s*(?:class|struct)\s+(?P<name>\w+)")),
        ("func", re.compile(r"^[\w:<>,\*&\s]+?\b(?P<name>\w+)\s*\([^;]*\)\s*\{?\s*$")),
    ],
    "C#": [
        ("class", re.compile(r"^\s*(?:public|private|internal|protected|\s)*"
                             r"(?:class|struct|interface|enum)\s+(?P<name>\w+)")),
        ("method", re.compile(r"^\s*(?:public|private|internal|protected|static|"
                              r"virtual|override|async|\s)+[\w<>,\[\]\.]+\s+"
                              r"(?P<name>\w+)\s*\([^;]*\)\s*\{?\s*$")),
    ],
}
# aliases that share a pattern set
_PATTERNS["C"] = _PATTERNS["C++"]
_PATTERNS["C/C++ Header"] = _PATTERNS["C++"]
_PATTERNS["C++ Header"] = _PATTERNS["C++"]

_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "catch", "else"}


def extract_symbols(text: str, language: str) -> list[tuple[int, int, str]]:
    """Return [(line, indent, stripped_def_text)] for class/func definitions."""
    patterns = _PATTERNS.get(language)
    if not patterns:
        return []
    out: list[tuple[int, int, str]] = []
    for i, line in enumerate(text.splitlines()):
        for _kind, rx in patterns:
            m = rx.match(line)
            if m and m.group("name") not in _KEYWORDS:
                indent = len(line) - len(line.lstrip())
                out.append((i, indent, line.strip()))
                break
    return out


class SymbolsPanel(QListWidget):
    symbol_activated = pyqtSignal(int)  # line number

    def __init__(self):
        super().__init__()
        self.itemActivated.connect(self._emit)
        self.itemClicked.connect(self._emit)

    def update_for(self, text: str, language: str) -> None:
        self.clear()
        patterns = _PATTERNS.get(language)
        if not patterns:
            return
        _KW = {"if", "for", "while", "switch", "return", "sizeof", "catch", "else"}
        for i, line in enumerate(text.splitlines()):
            for kind, rx in patterns:
                m = rx.match(line)
                if m:
                    name = m.group("name")
                    if name in _KW:
                        continue
                    item = QListWidgetItem(f"{self._icon(kind)}  {name}")
                    item.setData(Qt.ItemDataRole.UserRole, i)
                    item.setToolTip(f"{kind} (line {i + 1})")
                    self.addItem(item)
                    break

    @staticmethod
    def _icon(kind: str) -> str:
        return {
            "class": "◆", "struct": "◆", "def": "ƒ",
            "func": "ƒ", "method": "ƒ",
        }.get(kind, "•")

    def _emit(self, item: QListWidgetItem) -> None:
        line = item.data(Qt.ItemDataRole.UserRole)
        if line is not None:
            self.symbol_activated.emit(int(line))
