"""Status bar: git branch, language, cursor position, encoding."""
from __future__ import annotations

from PyQt6.QtWidgets import QStatusBar, QLabel


class StatusBar(QStatusBar):
    def __init__(self):
        super().__init__()
        self.setSizeGripEnabled(False)

        self.branch = QLabel("")
        self.blame = QLabel("")
        self.blame.setStyleSheet("color: #6c7086;")
        self.language = QLabel("Plain Text")
        self.position = QLabel("Ln 1, Col 1")
        self.encoding = QLabel("UTF-8")

        self.addWidget(self.branch)
        self.addWidget(self.blame, 1)
        self.addPermanentWidget(self.position)
        self.addPermanentWidget(self.language)
        self.addPermanentWidget(self.encoding)

    def set_branch(self, branch: str) -> None:
        self.branch.setText(f"  ⎇ {branch}" if branch else "")

    def set_blame(self, text: str) -> None:
        self.blame.setText(text)

    def set_language(self, language: str) -> None:
        self.language.setText(language)

    def set_position(self, line: int, col: int) -> None:
        self.position.setText(f"Ln {line + 1}, Col {col + 1}")
