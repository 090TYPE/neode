"""Sticky scroll — pin the enclosing function/class header(s) at the top of the
editor while scrolling. Click a header to jump to its definition.

Language-agnostic scope detection via indentation of regex-matched symbol lines
(see ui.symbols_panel.extract_symbols). Works well for Python and reasonably for
brace languages whose code is indented.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.Qsci import QsciScintilla

from ui.symbols_panel import extract_symbols

_MAX_LEVELS = 3


class _HeaderRow(QLabel):
    def __init__(self, text: str, line: int, on_click):
        super().__init__(text)
        self._line = line
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("StickyRow")

    def mousePressEvent(self, event):  # noqa: N802
        self._on_click(self._line)


class StickyScroll(QWidget):
    def __init__(self, editor_getter):
        super().__init__()
        self._get_editor = editor_getter
        self.editor: QsciScintilla | None = None
        self.enabled = True
        self._symbols: list[tuple[int, int, str]] = []

        self.setObjectName("StickyScroll")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.hide()

    # ------------------------------------------------------------ attach
    def attach(self, editor) -> None:
        if not self.enabled or editor is None:
            self.hide()
            return
        if self.editor is editor:
            self._symbols = extract_symbols(editor.text(), editor.language)
            self._update()
            return
        # disconnect old
        if self.editor is not None:
            try:
                self.editor.verticalScrollBar().valueChanged.disconnect(self._update)
                self.editor.cursorPositionChanged.disconnect(self._on_cursor)
            except Exception:
                pass
        self.editor = editor
        self.setParent(editor.viewport())
        self._symbols = extract_symbols(editor.text(), editor.language)
        editor.verticalScrollBar().valueChanged.connect(self._update)
        editor.cursorPositionChanged.connect(self._on_cursor)
        self._update()

    def _on_cursor(self, *args) -> None:
        self._update()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.hide()
        elif self.editor is not None:
            self._update()

    # ------------------------------------------------------------ render
    def _first_visible_doc_line(self) -> int:
        ed = self.editor
        fv = ed.SendScintilla(QsciScintilla.SCI_GETFIRSTVISIBLELINE)
        return ed.SendScintilla(QsciScintilla.SCI_DOCLINEFROMVISIBLE, fv)

    def _enclosing(self, top_line: int):
        if not self._symbols:
            return []
        indent_of = {}
        for line, indent, _txt in self._symbols:
            indent_of[line] = indent
        # indent of the top visible line
        target_indent = None
        for line, indent, _txt in self._symbols:
            if line <= top_line:
                target_indent = indent
        chain = []
        min_indent = 1 << 30
        for line, indent, txt in reversed(self._symbols):
            if line > top_line:
                continue
            if indent < min_indent:
                chain.append((line, indent, txt))
                min_indent = indent
            if indent == 0:
                break
        chain.reverse()
        # only keep headers that are scrolled above the viewport
        chain = [c for c in chain if c[0] < top_line]
        return chain[:_MAX_LEVELS]

    def _clear_rows(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _update(self, *args) -> None:
        ed = self.editor
        if ed is None or not self.enabled:
            self.hide()
            return
        top = self._first_visible_doc_line()
        chain = self._enclosing(top)
        self._clear_rows()
        if not chain:
            self.hide()
            return
        for line, indent, txt in chain:
            row = _HeaderRow("  " * 0 + txt, line, self._goto)
            self._layout.addWidget(row)
        # size and position the overlay across the text area
        th = ed.SendScintilla(QsciScintilla.SCI_TEXTHEIGHT, 0) or 18
        height = th * len(chain) + 6
        vp = ed.viewport()
        self.setGeometry(0, 0, vp.width(), height)
        self.raise_()
        self.show()

    def _goto(self, line: int) -> None:
        if self.editor is not None:
            self.editor.setCursorPosition(line, 0)
            self.editor.SendScintilla(QsciScintilla.SCI_SETFIRSTVISIBLELINE, line)
            self.editor.setFocus()
