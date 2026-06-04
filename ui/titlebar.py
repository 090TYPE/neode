"""Custom frameless-window title bar with drag-to-move and window controls."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QPoint


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._drag_pos: QPoint | None = None
        self.setObjectName("TitleBar")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self.title = QLabel("NeoIDE")
        self.title.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.title)
        layout.addStretch(1)

        self.btn_min = self._control("–", self.window.showMinimized)
        self.btn_max = self._control("▢", self._toggle_max)
        self.btn_close = self._control("✕", self.window.close)
        self.btn_close.setObjectName("closeButton")
        self.btn_close.setStyleSheet(
            "QPushButton#closeButton:hover { background-color: #f38ba8; color: #11111b; }"
        )
        for b in (self.btn_min, self.btn_max, self.btn_close):
            layout.addWidget(b)

    def _control(self, text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(32, 24)
        btn.setFlat(True)
        btn.clicked.connect(slot)
        return btn

    def set_title(self, text: str) -> None:
        self.title.setText(text)

    def _toggle_max(self) -> None:
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    # ------------------------------------------------------------ drag move
    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - \
                self.window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self.window.isMaximized():
                self.window.showNormal()
            self.window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self._toggle_max()
