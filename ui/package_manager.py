"""Package Manager tab — install/uninstall libraries for many languages.

Commands run in the integrated terminal (output streams live; pip uses the
project's virtual-env via the same resolver the Run button uses).
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton,
    QFrame
)
from PyQt6.QtCore import Qt

from core import packages


class PackageManager(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(12)

        title = QLabel("Packages")
        tf = title.font(); tf.setPointSize(tf.pointSize() + 8); tf.setBold(True)
        title.setFont(tf)
        outer.addWidget(title)

        sub = QLabel("Install libraries for Python, Node, Rust, Go, Ruby, PHP, "
                     ".NET and more. Output appears in the terminal.")
        sub.setStyleSheet("color: #6c7086;")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        # manager selector
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Manager"))
        self.manager = QComboBox()
        for mid in packages.ORDER:
            self.manager.addItem(packages.MANAGERS[mid].label, mid)
        self.manager.currentIndexChanged.connect(self._update_preview)
        mrow.addWidget(self.manager, 1)
        outer.addLayout(mrow)

        # package name + install / uninstall
        prow = QHBoxLayout()
        self.pkg = QLineEdit()
        self.pkg.setPlaceholderText("package name, e.g. numpy / express / serde")
        self.pkg.textChanged.connect(self._update_preview)
        self.pkg.returnPressed.connect(self.install)
        install_btn = QPushButton("Install")
        install_btn.setObjectName("runButton")
        install_btn.clicked.connect(self.install)
        uninstall_btn = QPushButton("Uninstall")
        uninstall_btn.clicked.connect(self.uninstall)
        prow.addWidget(self.pkg, 1)
        prow.addWidget(install_btn)
        prow.addWidget(uninstall_btn)
        outer.addLayout(prow)

        # secondary actions
        arow = QHBoxLayout()
        self.install_all_btn = QPushButton("Install from manifest")
        self.install_all_btn.clicked.connect(self.install_all)
        list_btn = QPushButton("List installed")
        list_btn.clicked.connect(self.list_installed)
        arow.addWidget(self.install_all_btn)
        arow.addWidget(list_btn)
        arow.addStretch(1)
        outer.addLayout(arow)

        # command preview
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(line)
        self.preview = QLabel("")
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("color: #a6adc8; font-family: 'JetBrains Mono';")
        outer.addWidget(self.preview)
        outer.addStretch(1)

        self.auto_select()

    # ------------------------------------------------------------ helpers
    def _root(self) -> str | None:
        return self.window.file_tree.root_path

    def current_manager(self) -> str:
        return self.manager.currentData()

    def auto_select(self) -> None:
        mid = packages.detect(self._root())
        idx = self.manager.findData(mid)
        if idx >= 0:
            self.manager.setCurrentIndex(idx)
        self._update_preview()

    def _update_preview(self) -> None:
        mid = self.current_manager()
        mgr = packages.MANAGERS[mid]
        self.install_all_btn.setText(mgr.install_all_label)
        cmd = packages.build(mid, "install", self._root(), self.pkg.text() or "<package>")
        self.preview.setText("$ " + cmd if cmd else
                             "This manager has no ad-hoc install command "
                             "(edit the build file instead).")

    def _run(self, command: str | None) -> None:
        if not command:
            self.window.status.showMessage("Not supported for this manager", 2500)
            return
        root = self._root()
        if root:
            self.window.terminal.set_workdir(root)
        self.window._show_terminal()
        self.window.terminal.run_command(command)

    # ------------------------------------------------------------ actions
    def install(self) -> None:
        name = self.pkg.text().strip()
        if not name:
            self.window.status.showMessage("Enter a package name", 2000)
            return
        self._run(packages.build(self.current_manager(), "install", self._root(), name))

    def uninstall(self) -> None:
        name = self.pkg.text().strip()
        if not name:
            self.window.status.showMessage("Enter a package name", 2000)
            return
        self._run(packages.build(self.current_manager(), "uninstall", self._root(), name))

    def install_all(self) -> None:
        self._run(packages.build(self.current_manager(), "install_all", self._root()))

    def list_installed(self) -> None:
        self._run(packages.build(self.current_manager(), "list", self._root()))
