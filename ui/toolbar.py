"""Slim action toolbar under the title bar: Run / Stop and quick actions."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QToolButton, QFrame, QLabel
from PyQt6.QtCore import Qt


class ActionToolBar(QWidget):
    def __init__(self, actions: dict):
        """actions: mapping of name -> callback for the known buttons."""
        super().__init__()
        self.setObjectName("ActionToolBar")
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        self.btn_run = self._button("▶  Run", "Run current file (F5)", actions.get("run"))
        self.btn_run.setObjectName("runButton")
        self.btn_stop = self._button("■  Stop", "Stop running process", actions.get("stop"))
        self.btn_stop.setEnabled(False)
        layout.addWidget(self.btn_run)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self._sep())

        for label, tip, key in [
            ("New", "New file (Ctrl+N)", "new"),
            ("Open", "Open folder (Ctrl+K Ctrl+O)", "open_folder"),
            ("Search", "Find in files (Ctrl+Shift+F)", "search"),
            ("📦 Packages", "Install libraries", "packages"),
        ]:
            layout.addWidget(self._button(label, tip, actions.get(key)))

        layout.addStretch(1)
        self.run_label = QLabel("")
        self.run_label.setStyleSheet("color: #6c7086;")
        layout.addWidget(self.run_label)
        layout.addWidget(self._sep())
        layout.addWidget(self._button("⌘ Palette", "Command palette (Ctrl+Shift+P)",
                                      actions.get("palette")))
        layout.addWidget(self._button("⚙", "Settings (Ctrl+,)", actions.get("settings")))

    def _button(self, text: str, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if slot:
            b.clicked.connect(slot)
        return b

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedHeight(18)
        return line

    def set_running(self, running: bool) -> None:
        self.btn_stop.setEnabled(running)
        self.btn_run.setEnabled(not running)
        self.run_label.setText("● running" if running else "")

    def set_run_hint(self, text: str) -> None:
        if not self.btn_stop.isEnabled():
            self.run_label.setText(text)
