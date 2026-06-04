"""AI assistant — chat panel + explain/refactor the current selection.

Talks to the Anthropic Messages API over HTTPS on a background thread. Needs an
API key in Settings (`anthropic_api_key`); without one it explains how to add it.
"""
from __future__ import annotations

import json
import threading
import urllib.request

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QLineEdit, QPushButton, QLabel
)
from PyQt6.QtCore import pyqtSignal

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-3-5-haiku-20241022"


class AiAssistant(QWidget):
    _reply = pyqtSignal(str)

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._messages: list[dict] = []
        self._busy = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        layout.addWidget(self.view, 1)

        actions = QHBoxLayout()
        explain = QPushButton("Explain selection")
        explain.clicked.connect(lambda: self._on_code("Explain this code clearly:"))
        refactor = QPushButton("Refactor")
        refactor.clicked.connect(
            lambda: self._on_code("Refactor this code for clarity; return only the "
                                  "improved code in a fenced block:"))
        actions.addWidget(explain)
        actions.addWidget(refactor)
        layout.addLayout(actions)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask anything…")
        self.input.returnPressed.connect(self.send)
        send = QPushButton("Send")
        send.setObjectName("runButton")
        send.clicked.connect(self.send)
        row.addWidget(self.input, 1)
        row.addWidget(send)
        layout.addLayout(row)

        self._reply.connect(self._on_reply)
        self._append("**AI assistant.** Add an Anthropic API key in Settings to start. "
                     "Then ask a question or select code and click Explain/Refactor.")

    # ------------------------------------------------------------ helpers
    def _key(self) -> str:
        return getattr(self.window.settings, "anthropic_api_key", "") or ""

    def _append(self, markdown: str) -> None:
        self.view.append(markdown + "\n")

    def _on_code(self, instruction: str) -> None:
        editor = self.window.active_editor()
        if editor is None:
            return
        code = editor.selectedText() or editor.text()
        if not code.strip():
            self.window.status.showMessage("Nothing to send", 2000)
            return
        lang = editor.language
        self.send(f"{instruction}\n\n```{lang}\n{code}\n```")

    def send(self, prompt: str | None = None) -> None:
        if self._busy:
            return
        text = prompt if isinstance(prompt, str) and prompt else self.input.text().strip()
        if not text:
            return
        if not self._key():
            self._append("⚠ No API key. Open **Settings → Tools** and paste your "
                         "Anthropic API key into *Anthropic API key*.")
            return
        self.input.clear()
        self._append(f"**You:** {text}")
        self._messages.append({"role": "user", "content": text})
        self._busy = True
        self._append("_thinking…_")
        threading.Thread(target=self._call_api, daemon=True).start()

    def _call_api(self) -> None:
        try:
            body = json.dumps({
                "model": _MODEL,
                "max_tokens": 1024,
                "messages": self._messages[-12:],
            }).encode("utf-8")
            req = urllib.request.Request(_API_URL, data=body, method="POST", headers={
                "x-api-key": self._key(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            parts = data.get("content", [])
            text = "".join(p.get("text", "") for p in parts) or "(empty response)"
        except Exception as e:  # noqa: BLE001
            text = f"⚠ Request failed: {e}"
        self._reply.emit(text)

    def _on_reply(self, text: str) -> None:
        self._busy = False
        self._messages.append({"role": "assistant", "content": text})
        self._append(f"**Claude:** {text}")
