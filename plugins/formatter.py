"""Built-in plugin: format the current file via clang-format / dotnet format."""
from __future__ import annotations

from pathlib import Path

from plugins.base import BasePlugin


class Plugin(BasePlugin):
    name = "Formatter"
    version = "1.0.0"

    def activate(self) -> None:
        self.api.ui.register_command("Format Document", self.format, "Shift+Alt+F")

    def format(self) -> None:
        path = self.api.editor.current_path()
        if not path:
            self.api.ui.show_notification("Save the file before formatting", 2500)
            return
        ext = Path(path).suffix.lower()
        if ext in (".cpp", ".cc", ".cxx", ".c", ".h", ".hpp"):
            self.api.terminal.run(f"clang-format -i {path}")
            self.api.ui.show_notification("Ran clang-format", 2000)
        elif ext == ".cs":
            self.api.terminal.run("dotnet format")
            self.api.ui.show_notification("Ran dotnet format", 2000)
        else:
            self.api.ui.show_notification(f"No formatter for {ext}", 2500)
