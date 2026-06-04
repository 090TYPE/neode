"""Integrated terminal: QProcess-backed output + command input.

Runs the current file across many languages (compile+execute chained with &&),
streams output, parses compiler diagnostics so clicking a line jumps into the
editor, and exposes Stop/Clear plus a running-state signal for the toolbar.
"""
from __future__ import annotations

import re
import os
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLineEdit, QToolButton,
    QLabel
)
from PyQt6.QtCore import QProcess, pyqtSignal
from PyQt6.QtGui import QTextCursor

from core.runners import build_command

# matches: main.cpp:10:5: error: ...   /   Program.cs(10,5): error CS....
GCC_RE = re.compile(r"^(.*?):(\d+):(\d+):\s*(error|warning):\s*(.*)$")
MSVC_RE = re.compile(r"^(.*?)\((\d+),(\d+)\):\s*(error|warning)\s*\w*:\s*(.*)$")


class Terminal(QWidget):
    error_clicked = pyqtSignal(str, int, int)   # (file_path, line, col)
    running_changed = pyqtSignal(bool)
    # (file_path, line, col, severity, message) parsed from compiler output
    diagnostic_found = pyqtSignal(str, int, int, int, str)

    def __init__(self):
        super().__init__()
        self.process: QProcess | None = None
        self.workdir = os.getcwd()
        self._start_time = 0.0
        self._line_buf = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # header: status + Stop / Clear
        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 4)
        self.status_label = QLabel("Terminal")
        self.status_label.setStyleSheet("color: #6c7086;")
        self.btn_stop = QToolButton()
        self.btn_stop.setText("■ Stop")
        self.btn_stop.setToolTip("Stop the running process")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_stop.setEnabled(False)
        self.btn_clear = QToolButton()
        self.btn_clear.setText("Clear")
        self.btn_clear.clicked.connect(self.clear)
        header.addWidget(self.status_label, 1)
        header.addWidget(self.btn_stop)
        header.addWidget(self.btn_clear)
        layout.addLayout(header)

        self.output = QPlainTextEdit(readOnly=True)
        self.output.setMaximumBlockCount(8000)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command and press Enter…")
        self.input.returnPressed.connect(self._on_enter)
        self.output.mouseDoubleClickEvent = self._on_output_double_click  # type: ignore

        layout.addWidget(self.output, 1)
        layout.addWidget(self.input)

    # ------------------------------------------------------------ helpers
    def set_workdir(self, path: str) -> None:
        self.workdir = path

    def is_running(self) -> bool:
        return self.process is not None and \
            self.process.state() != QProcess.ProcessState.NotRunning

    def clear(self) -> None:
        self.output.clear()

    def stop(self) -> None:
        if self.is_running():
            self._append("\n[stopped by user]\n")
            self.process.kill()
            self.process.waitForFinished(1000)

    # ------------------------------------------------------------ process I/O
    def _new_process(self, banner: str) -> QProcess:
        self._ensure_killed()
        self._line_buf = ""
        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.workdir)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)
        self._append(f"$ {banner}\n")
        self._start_time = time.monotonic()
        return self.process

    def run_command(self, command: str) -> None:
        """Run an arbitrary shell command string in the working directory.

        On Windows we use ``cmd /s /c "<command>"`` via setNativeArguments so that
        quoted paths (e.g. a venv python) are passed through verbatim instead of
        being re-quoted by QProcess.
        """
        proc = self._new_process(command)
        if os.name == "nt":
            proc.setProgram("cmd.exe")
            proc.setNativeArguments(f'/s /c "{command}"')
            proc.start()
        else:
            proc.start("/bin/bash", ["-lc", command])
        self._set_running(True)

    def _ensure_killed(self) -> None:
        if self.is_running():
            self.process.kill()
            self.process.waitForFinished(1000)

    def _read(self) -> None:
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        self._append(data)
        self._scan_diagnostics(data)

    def _scan_diagnostics(self, data: str) -> None:
        self._line_buf += data
        *lines, self._line_buf = self._line_buf.split("\n")
        for line in lines:
            match = GCC_RE.match(line.strip()) or MSVC_RE.match(line.strip())
            if not match:
                continue
            file = match.group(1)
            row = int(match.group(2))
            col = int(match.group(3))
            severity = 1 if match.group(4).lower() == "error" else 2
            message = match.group(5)
            full = file if Path(file).is_absolute() else str(Path(self.workdir) / file)
            self.diagnostic_found.emit(full, row - 1, max(col - 1, 0), severity, message)

    def _on_finished(self, code: int, _status) -> None:
        elapsed = time.monotonic() - self._start_time
        tag = "✓" if code == 0 else "✗"
        self._append(f"\n[{tag} exited with code {code} in {elapsed:.2f}s]\n")
        self._set_running(False)

    def _on_error(self, _err) -> None:
        if self.process is not None:
            self._append(f"\n[failed to start: {self.process.errorString()}]\n")
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.btn_stop.setEnabled(running)
        self.status_label.setText("Running…" if running else "Terminal")
        self.running_changed.emit(running)

    def _append(self, text: str) -> None:
        self.output.moveCursor(QTextCursor.MoveOperation.End)
        self.output.insertPlainText(text)
        self.output.moveCursor(QTextCursor.MoveOperation.End)

    def _on_enter(self) -> None:
        cmd = self.input.text().strip()
        self.input.clear()
        if cmd:
            self.run_command(cmd)

    # ------------------------------------------------------------ run code
    def run_file(self, file_path: str) -> None:
        path = Path(file_path)
        self.set_workdir(str(path.parent))
        command = build_command(file_path)
        if command is None:
            self._append(f"[don't know how to run {path.suffix} files]\n")
            return
        self.run_command(command)

    # ------------------------------------------------------------ click->jump
    def _on_output_double_click(self, event) -> None:
        cursor = self.output.cursorForPosition(event.pos())
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText()
        match = GCC_RE.match(line) or MSVC_RE.match(line)
        if match:
            file = match.group(1)
            row = int(match.group(2))
            col = int(match.group(3))
            full = file if Path(file).is_absolute() else str(Path(self.workdir) / file)
            self.error_clicked.emit(full, row - 1, max(col - 1, 0))
        QPlainTextEdit.mouseDoubleClickEvent(self.output, event)
