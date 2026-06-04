"""Live Markdown preview tab backed by QTextBrowser.setMarkdown (Qt built-in).

Holds a weak link to the source editor; while the preview tab is open it
re-renders (debounced) whenever the editor text changes.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer


class MarkdownPreview(QWidget):
    def __init__(self, editor, title: str):
        super().__init__()
        self.editor = editor

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(10, 6, 10, 6)
        label = QLabel(f"Preview — {title}")
        label.setStyleSheet("color: #6c7086;")
        header.addWidget(label)
        header.addStretch(1)
        layout.addLayout(header)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        layout.addWidget(self.view, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.refresh)

        if editor is not None:
            editor.textChanged.connect(self._timer.start)
        self.refresh()

    def refresh(self) -> None:
        if self.editor is None:
            return
        try:
            self.view.setMarkdown(self.editor.text())
        except Exception:
            self.view.setPlainText(self.editor.text())
