"""Built-in plugin: scan the current file for TODO / FIXME markers."""
from __future__ import annotations

import re

from plugins.base import BasePlugin

MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b[:\s]?(.*)", re.IGNORECASE)


class Plugin(BasePlugin):
    name = "TODO Tree"
    version = "1.0.0"

    def activate(self) -> None:
        self.api.ui.register_command("Find TODOs in File", self.scan)

    def scan(self) -> None:
        text = self.api.editor.get_text()
        hits = []
        for i, line in enumerate(text.splitlines(), start=1):
            m = MARKER_RE.search(line)
            if m:
                hits.append(f"{i}: {m.group(1).upper()} {m.group(2).strip()}")
        if hits:
            self.api.ui.show_notification(f"{len(hits)} TODO(s) — {hits[0]}", 5000)
        else:
            self.api.ui.show_notification("No TODOs found", 2000)
