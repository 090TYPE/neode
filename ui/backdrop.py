"""Backdrop — the application's central widget. Paints an optional wallpaper
image plus a theme-coloured overlay behind every other widget.

Chrome widgets above it are made translucent (via QSS rgba) so the wallpaper
shows through. When no image is set it simply fills with the theme background,
so the IDE looks completely normal.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPixmap, QColor
from PyQt6.QtCore import Qt, QRect


class Backdrop(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Backdrop")
        self._pixmap: QPixmap | None = None
        self._mode = "cover"
        self._overlay = QColor("#1e1e2e")
        self._overlay_alpha = 160  # 0..255 strength of the colour wash

    # ------------------------------------------------------------ config
    def set_base_color(self, hex_color: str) -> None:
        c = QColor(hex_color)
        if c.isValid():
            self._overlay = c
            self.update()

    def set_image(self, path: str, mode: str, opacity: int) -> None:
        """opacity 0..100 — how visible the image is (100 = no colour wash)."""
        if path and Path(path).exists():
            pix = QPixmap(path)
            self._pixmap = pix if not pix.isNull() else None
        else:
            self._pixmap = None
        self._mode = mode or "cover"
        self._overlay_alpha = int(max(0, min(100, 100 - opacity)) / 100 * 255)
        self.update()

    def clear_image(self) -> None:
        self._pixmap = None
        self.update()

    # ------------------------------------------------------------ painting
    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        rect = self.rect()
        if self._pixmap is None:
            p.fillRect(rect, self._overlay)
            return
        self._paint_image(p, rect)
        wash = QColor(self._overlay)
        wash.setAlpha(self._overlay_alpha)
        p.fillRect(rect, wash)

    def _paint_image(self, p: QPainter, rect: QRect) -> None:
        pix = self._pixmap
        if pix is None or pix.isNull():
            return
        mode = self._mode
        if mode == "stretch":
            p.drawPixmap(rect, pix)
        elif mode == "center":
            x = rect.x() + (rect.width() - pix.width()) // 2
            y = rect.y() + (rect.height() - pix.height()) // 2
            p.drawPixmap(x, y, pix)
        elif mode == "tile":
            p.drawTiledPixmap(rect, pix)
        elif mode == "contain":
            scaled = pix.scaled(
                rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() + (rect.width() - scaled.width()) // 2
            y = rect.y() + (rect.height() - scaled.height()) // 2
            p.fillRect(rect, self._overlay)
            p.drawPixmap(x, y, scaled)
        else:  # cover
            scaled = pix.scaled(
                rect.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() + (rect.width() - scaled.width()) // 2
            y = rect.y() + (rect.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
