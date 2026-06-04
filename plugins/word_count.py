"""Built-in plugin: live line / word / char counts in the status bar.

Demonstrates: api.statusbar.add_text() and subscribing to events.
"""
from __future__ import annotations

from plugins.base import BasePlugin


class Plugin(BasePlugin):
    name = "Word Count"
    version = "1.0.0"
    author = "NeoIDE"
    description = "Shows line, word and character counts of the active file in the status bar."

    def activate(self) -> None:
        self.label = self.api.statusbar.add_text("")
        # update on cursor move, file open and save
        self.api.window.tabs.cursor_moved.connect(self._update)
        self.api.events.on("file_opened", lambda *_a: self._update())
        self.api.events.on("file_saved", lambda *_a: self._update())
        self._update()

    def _update(self, *args) -> None:
        text = self.api.editor.get_text()
        lines = text.count("\n") + 1 if text else 0
        words = len(text.split())
        chars = len(text)
        self.label.setText(f"{lines} ln · {words} words · {chars} chars")

    def deactivate(self) -> None:
        self.label.setText("")
        try:
            self.api.statusbar.remove(self.label)
        except Exception:
            pass
