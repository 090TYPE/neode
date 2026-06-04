"""Multiple integrated terminals in tabs. Delegates the Terminal API to the
active tab so the rest of the app treats it like a single terminal."""
from __future__ import annotations

import os

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QToolButton
from PyQt6.QtCore import pyqtSignal

from core.terminal import Terminal


class TerminalTabs(QWidget):
    error_clicked = pyqtSignal(str, int, int)
    running_changed = pyqtSignal(bool)
    diagnostic_found = pyqtSignal(str, int, int, int, str)

    def __init__(self):
        super().__init__()
        self._workdir = os.getcwd()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close)

        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip("New terminal")
        add_btn.clicked.connect(lambda: self.add_terminal())
        self.tabs.setCornerWidget(add_btn)

        layout.addWidget(self.tabs)
        self.add_terminal()

    # ------------------------------------------------------------ management
    def add_terminal(self) -> Terminal:
        term = Terminal()
        term.set_workdir(self._workdir)
        term.error_clicked.connect(self.error_clicked)
        term.running_changed.connect(self.running_changed)
        term.diagnostic_found.connect(self.diagnostic_found)
        idx = self.tabs.addTab(term, f"Terminal {self.tabs.count() + 1}")
        self.tabs.setCurrentIndex(idx)
        return term

    def _close(self, index: int) -> None:
        if self.tabs.count() <= 1:
            self.current().clear()
            return
        w = self.tabs.widget(index)
        if isinstance(w, Terminal):
            w.stop()
        self.tabs.removeTab(index)

    def current(self) -> Terminal:
        w = self.tabs.currentWidget()
        return w if isinstance(w, Terminal) else self.add_terminal()

    # ------------------------------------------------------------ Terminal API
    def set_workdir(self, path: str) -> None:
        self._workdir = path
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, Terminal):
                w.set_workdir(path)

    def run_command(self, command: str) -> None:
        self.current().run_command(command)

    def run_file(self, path: str) -> None:
        self.current().run_file(path)

    def clear(self) -> None:
        self.current().clear()

    def stop(self) -> None:
        self.current().stop()

    def is_running(self) -> bool:
        return self.current().is_running()
