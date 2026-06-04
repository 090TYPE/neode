"""Minimal Language Server Protocol client.

Speaks JSON-RPC over a language server's stdin/stdout on a background QThread so
the UI never blocks. Currently wires up initialize / didOpen / didChange and
surfaces publishDiagnostics; completion and definition requests are provided as
helpers ready for the UI to consume.

Design note: this is intentionally dependency-free (no python-lsp-jsonrpc) so it
stays transparent — the framing is the standard ``Content-Length`` header + JSON
body described at microsoft.github.io/language-server-protocol.
"""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

# extension -> server command (override paths via Settings if needed)
SERVERS = {
    ".cpp": ["clangd"], ".cc": ["clangd"], ".cxx": ["clangd"],
    ".c": ["clangd"], ".h": ["clangd"], ".hpp": ["clangd"],
    ".cs": ["omnisharp", "-lsp"],
}


def uri_for(path: str) -> str:
    return Path(path).resolve().as_uri()


class LspClient(QObject):
    diagnostics = pyqtSignal(str, list)   # (file_path, list[diagnostic dict])
    initialized = pyqtSignal()
    completions = pyqtSignal(list)        # list[str] of completion labels
    definition_found = pyqtSignal(str, int, int)  # (path, line, col)

    def __init__(self, command: list[str], root: str):
        super().__init__()
        self.command = command
        self.root = root
        self.proc: subprocess.Popen | None = None
        self._id = 0
        self._reader: threading.Thread | None = None
        self._alive = False
        self._pending: dict[int, str] = {}  # id -> method, for routing replies

    # ------------------------------------------------------------- lifecycle
    def start(self) -> bool:
        try:
            self.proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, OSError):
            return False
        self._alive = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._initialize()
        return True

    def stop(self) -> None:
        self._alive = False
        if self.proc:
            try:
                self._notify("exit", {})
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

    # ------------------------------------------------------------- messaging
    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, payload: dict) -> None:
        if not self.proc or not self.proc.stdin:
            return
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            self.proc.stdin.write(header + body)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self._alive = False

    def _request(self, method: str, params: dict) -> int:
        rid = self._next_id()
        self._pending[rid] = method
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return rid

    def _notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    # ------------------------------------------------------------- handshake
    def _initialize(self) -> None:
        self._request("initialize", {
            "processId": None,
            "rootUri": Path(self.root).resolve().as_uri(),
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True, "dynamicRegistration": False},
                    "completion": {"completionItem": {"snippetSupport": False}},
                    "publishDiagnostics": {"relatedInformation": True},
                    "hover": {}, "definition": {},
                }
            },
        })

    # ------------------------------------------------------------- documents
    def did_open(self, path: str, text: str, language_id: str) -> None:
        self._notify("textDocument/didOpen", {
            "textDocument": {
                "uri": uri_for(path), "languageId": language_id,
                "version": 1, "text": text,
            }
        })

    def did_change(self, path: str, text: str, version: int) -> None:
        # full-document sync (simplest correct strategy)
        self._notify("textDocument/didChange", {
            "textDocument": {"uri": uri_for(path), "version": version},
            "contentChanges": [{"text": text}],
        })

    def request_completion(self, path: str, line: int, col: int) -> int:
        return self._request("textDocument/completion", {
            "textDocument": {"uri": uri_for(path)},
            "position": {"line": line, "character": col},
        })

    def request_definition(self, path: str, line: int, col: int) -> int:
        return self._request("textDocument/definition", {
            "textDocument": {"uri": uri_for(path)},
            "position": {"line": line, "character": col},
        })

    # ------------------------------------------------------------- read loop
    def _read_loop(self) -> None:
        stream = self.proc.stdout if self.proc else None
        if stream is None:
            return
        while self._alive:
            try:
                headers = {}
                while True:
                    line = stream.readline()
                    if not line:
                        return
                    line = line.decode("ascii", errors="replace").strip()
                    if line == "":
                        break
                    if ":" in line:
                        key, _, value = line.partition(":")
                        headers[key.strip().lower()] = value.strip()
                length = int(headers.get("content-length", 0))
                if length <= 0:
                    continue
                body = stream.read(length)
                message = json.loads(body.decode("utf-8"))
                self._dispatch(message)
            except Exception:
                if not self._alive:
                    return
                continue

    def _dispatch(self, message: dict) -> None:
        method = message.get("method")
        if method == "textDocument/publishDiagnostics":
            params = message.get("params", {})
            uri = params.get("uri", "")
            path = self._uri_to_path(uri)
            self.diagnostics.emit(path, params.get("diagnostics", []))
            return
        if "id" not in message or "result" not in message:
            return
        rid = message.get("id")
        result = message.get("result")
        requested = self._pending.pop(rid, None)
        if requested == "initialize" or rid == 1:
            self._notify("initialized", {})
            self.initialized.emit()
        elif requested == "textDocument/completion":
            self.completions.emit(self._parse_completions(result))
        elif requested == "textDocument/definition":
            self._emit_definition(result)

    def _parse_completions(self, result) -> list[str]:
        items = result.get("items", result) if isinstance(result, dict) else result
        labels = []
        for item in items or []:
            label = item.get("insertText") or item.get("label")
            if label:
                labels.append(label.strip())
        # de-duplicate, keep order, cap for a usable popup
        seen, out = set(), []
        for label in labels:
            if label not in seen:
                seen.add(label)
                out.append(label)
        return out[:100]

    def _emit_definition(self, result) -> None:
        loc = result[0] if isinstance(result, list) and result else result
        if not isinstance(loc, dict):
            return
        uri = loc.get("uri") or loc.get("targetUri")
        rng = loc.get("range") or loc.get("targetSelectionRange") or {}
        start = rng.get("start", {})
        if uri:
            self.definition_found.emit(
                self._uri_to_path(uri), start.get("line", 0), start.get("character", 0)
            )

    @staticmethod
    def _uri_to_path(uri: str) -> str:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(uri)
        path = unquote(parsed.path)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]  # Windows drive: /C:/... -> C:/...
        return path


class LspManager:
    """Owns one LspClient per language, keyed by server command."""

    def __init__(self, root: str, settings=None):
        self.root = root
        self.settings = settings
        self.clients: dict[str, LspClient] = {}

    def client_for(self, file_path: str) -> LspClient | None:
        ext = Path(file_path).suffix.lower()
        command = self._resolve(ext)
        if command is None:
            return None
        key = command[0]
        if key not in self.clients:
            client = LspClient(command, self.root)
            if not client.start():
                return None
            self.clients[key] = client
        return self.clients[key]

    def _resolve(self, ext: str) -> list[str] | None:
        command = SERVERS.get(ext)
        if command is None:
            return None
        command = list(command)
        if self.settings:
            if command[0] == "clangd" and self.settings.clangd_path:
                command[0] = self.settings.clangd_path
            elif command[0] == "omnisharp" and self.settings.omnisharp_path:
                command[0] = self.settings.omnisharp_path
        return command

    def shutdown(self) -> None:
        for client in self.clients.values():
            client.stop()
        self.clients.clear()
