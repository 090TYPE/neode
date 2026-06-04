"""Minimap — a tiny code overview on the right of the editor.

Mirrors the target editor's text (read-only, tiny font). A translucent box
shows the visible region; click/drag scrolls the main editor. Text is copied on
attach and on edits (debounced) which is simple and crash-free (unlike sharing
Scintilla document pointers).
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QTimer
from PyQt6.Qsci import QsciScintilla


class _Indicator(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.top = 0
        self.height_px = 40
        self.color = QColor(255, 255, 255, 32)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.fillRect(0, self.top, self.width(), self.height_px, self.color)


class Minimap(QsciScintilla):
    def __init__(self, get_editor):
        super().__init__()
        self._get_editor = get_editor
        self.editor: QsciScintilla | None = None
        self.enabled = True

        self.setReadOnly(True)
        self.setFixedWidth(110)
        self.setCaretLineVisible(False)
        self.setCaretWidth(0)
        for m in range(3):
            self.setMarginWidth(m, 0)
        self.SendScintilla(QsciScintilla.SCI_SETVSCROLLBAR, 0)
        self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)
        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("JetBrains Mono", 2))

        self._indicator = _Indicator(self)
        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.setInterval(300)
        self._copy_timer.timeout.connect(self._copy_text)
        self.hide()

    # ------------------------------------------------------------ attach
    def attach(self, editor) -> None:
        if not self.enabled or editor is None:
            self.hide()
            return
        if self.editor is not editor:
            if self.editor is not None:
                try:
                    self.editor.verticalScrollBar().valueChanged.disconnect(self._sync)
                    self.editor.textChanged.disconnect(self._copy_timer.start)
                except Exception:
                    pass
            self.editor = editor
            editor.verticalScrollBar().valueChanged.connect(self._sync)
            editor.textChanged.connect(self._copy_timer.start)
            self._apply_colors(editor)
        self._copy_text()
        self.show()
        self._sync()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.hide()
        elif self.editor is not None:
            self.show()
            self._copy_text()
            self._sync()

    # ------------------------------------------------------------ helpers
    def _copy_text(self) -> None:
        ed = self.editor
        if ed is None or not self.enabled:
            return
        self.setReadOnly(False)
        self.setText(ed.text())
        self.setReadOnly(True)
        self._sync()

    def _apply_colors(self, editor) -> None:
        bg = getattr(editor, "_paper_color", QColor("#1e1e2e"))
        self.setPaper(QColor(bg))
        self.setColor(QColor("#9aa0a6"))
        try:
            self.SendScintilla(QsciScintilla.SCI_STYLESETBACK, 0,
                               QColor(bg).rgb() & 0xFFFFFF)
            self.SendScintilla(QsciScintilla.SCI_STYLESETSIZE, 0, 2)
        except Exception:
            pass

    def _sync(self, *args) -> None:
        ed = self.editor
        if ed is None or not self.enabled or not self.isVisible():
            return
        first = ed.SendScintilla(QsciScintilla.SCI_GETFIRSTVISIBLELINE)
        visible = max(ed.SendScintilla(QsciScintilla.SCI_LINESONSCREEN), 1)
        mm_on_screen = max(self.SendScintilla(QsciScintilla.SCI_LINESONSCREEN), 1)
        new_first = max(0, first - (mm_on_screen - visible) // 2)
        self.SendScintilla(QsciScintilla.SCI_SETFIRSTVISIBLELINE, new_first)
        mm_first = self.SendScintilla(QsciScintilla.SCI_GETFIRSTVISIBLELINE)
        th = self.SendScintilla(QsciScintilla.SCI_TEXTHEIGHT, 0) or 2
        self._indicator.setGeometry(0, 0, self.width(), self.height())
        self._indicator.top = max(0, (first - mm_first) * th)
        self._indicator.height_px = max(8, visible * th)
        self._indicator.update()

    # ------------------------------------------------------------ navigation
    def _scroll_editor_to_y(self, y: int) -> None:
        ed = self.editor
        if ed is None:
            return
        mm_first = self.SendScintilla(QsciScintilla.SCI_GETFIRSTVISIBLELINE)
        th = self.SendScintilla(QsciScintilla.SCI_TEXTHEIGHT, 0) or 2
        target = mm_first + int(y / th)
        visible = max(ed.SendScintilla(QsciScintilla.SCI_LINESONSCREEN), 1)
        ed.SendScintilla(QsciScintilla.SCI_SETFIRSTVISIBLELINE,
                         max(0, target - visible // 2))
        self._sync()

    def mousePressEvent(self, event):  # noqa: N802
        self._scroll_editor_to_y(int(event.position().y()))

    def mouseMoveEvent(self, event):  # noqa: N802
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._scroll_editor_to_y(int(event.position().y()))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._indicator.setGeometry(0, 0, self.width(), self.height())
