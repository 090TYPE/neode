"""Built-in plugin: strip trailing whitespace from each line on save.

Demonstrates: the ``before_save`` event, which may modify the editor buffer
before it is written to disk. Toggle it from the command palette.
"""
from __future__ import annotations

from plugins.base import BasePlugin


class Plugin(BasePlugin):
    name = "Trim Whitespace on Save"
    version = "1.0.0"
    author = "NeoIDE"
    description = "Removes trailing spaces/tabs from every line right before the file is saved."

    def activate(self) -> None:
        self.enabled = self.storage.get("enabled", True)
        self.api.events.on("before_save", self._on_before_save)
        self.api.ui.register_command("Toggle Trim Whitespace on Save", self._toggle)

    def _toggle(self) -> None:
        self.enabled = not self.enabled
        self.storage.set("enabled", self.enabled)
        state = "on" if self.enabled else "off"
        self.api.ui.show_notification(f"Trim whitespace on save: {state}", 2000)

    def _on_before_save(self, editor, _path) -> None:
        if not self.enabled:
            return
        text = editor.text()
        trimmed = "\n".join(line.rstrip() for line in text.split("\n"))
        if trimmed != text:
            line, col = editor.getCursorPosition()
            editor.setText(trimmed)
            editor.setCursorPosition(line, col)
