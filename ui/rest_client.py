"""A minimal REST client tab — send HTTP requests and view the response.

Requests run on a background thread (urllib) so the UI never blocks.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, QPushButton,
    QPlainTextEdit, QLabel, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal


class RestClient(QWidget):
    _result = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("REST Client")
        tf = title.font(); tf.setPointSize(tf.pointSize() + 6); tf.setBold(True)
        title.setFont(tf)
        layout.addWidget(title)

        row = QHBoxLayout()
        self.method = QComboBox()
        self.method.addItems(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://api.example.com/endpoint")
        self.url.returnPressed.connect(self.send)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("runButton")
        self.send_btn.clicked.connect(self.send)
        row.addWidget(self.method)
        row.addWidget(self.url, 1)
        row.addWidget(self.send_btn)
        layout.addLayout(row)

        split = QSplitter(Qt.Orientation.Vertical)
        req = QWidget(); rl = QVBoxLayout(req); rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("Headers (one per line: Key: Value)"))
        self.headers = QPlainTextEdit()
        self.headers.setPlaceholderText("Content-Type: application/json")
        self.headers.setFixedHeight(70)
        rl.addWidget(self.headers)
        rl.addWidget(QLabel("Body"))
        self.body = QPlainTextEdit()
        self.body.setPlaceholderText('{\n  "key": "value"\n}')
        rl.addWidget(self.body)
        split.addWidget(req)

        resp = QWidget(); pl = QVBoxLayout(resp); pl.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel("Response")
        self.status.setStyleSheet("color: #6c7086;")
        pl.addWidget(self.status)
        self.response = QPlainTextEdit(readOnly=True)
        pl.addWidget(self.response)
        split.addWidget(resp)
        split.setSizes([200, 320])
        layout.addWidget(split, 1)

        self._result.connect(self._show_result)

    # ------------------------------------------------------------ send
    def send(self) -> None:
        url = self.url.text().strip()
        if not url:
            return
        if "://" not in url:
            url = "https://" + url
        method = self.method.currentText()
        headers = {}
        for line in self.headers.toPlainText().splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip()] = v.strip()
        body = self.body.toPlainText().encode("utf-8") if method not in ("GET", "HEAD") \
            and self.body.toPlainText().strip() else None

        self.send_btn.setEnabled(False)
        self.status.setText("Sending…")
        threading.Thread(target=self._do_request,
                         args=(method, url, headers, body), daemon=True).start()

    def _do_request(self, method, url, headers, body) -> None:
        started = time.monotonic()
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                elapsed = (time.monotonic() - started) * 1000
                head = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
                text = self._pretty(raw, resp.headers.get("Content-Type", ""))
                out = (f"STATUS {resp.status} {resp.reason}  ·  {elapsed:.0f} ms\n"
                       f"{'-'*50}\n{head}\n{'-'*50}\n{text}")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
            out = f"HTTP {e.code} {e.reason}\n{'-'*50}\n{raw}"
        except Exception as e:  # noqa: BLE001
            out = f"Request failed: {e}"
        self._result.emit(out)

    @staticmethod
    def _pretty(raw: str, content_type: str) -> str:
        if "json" in content_type.lower():
            try:
                return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                return raw
        return raw

    def _show_result(self, text: str) -> None:
        self.send_btn.setEnabled(True)
        first = text.splitlines()[0] if text else ""
        self.status.setText(first)
        self.response.setPlainText(text)
