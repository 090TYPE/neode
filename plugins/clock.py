"""Built-in plugin: a small clock in the status bar.

Demonstrates a plugin that owns a QTimer and a status-bar widget.
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer

from plugins.base import BasePlugin


class Plugin(BasePlugin):
    name = "Clock"
    version = "1.0.0"
    author = "NeoIDE"
    description = "Shows the current time in the status bar, updated every second."

    def activate(self) -> None:
        self.label = self.api.statusbar.add_text("")
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self._tick()

    def _tick(self) -> None:
        self.label.setText(datetime.now().strftime("%H:%M:%S"))

    def deactivate(self) -> None:
        self.timer.stop()
        try:
            self.api.statusbar.remove(self.label)
        except Exception:
            pass
