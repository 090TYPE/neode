"""Plugin Manager tab — list, enable/disable, reload and locate plugins."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame,
    QCheckBox
)
from PyQt6.QtCore import Qt


class _PluginCard(QFrame):
    def __init__(self, record, loader, on_change):
        super().__init__()
        self.record = record
        self.loader = loader
        self.on_change = on_change
        self.setObjectName("PluginCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(4)

        top = QHBoxLayout()
        name = QLabel(record.name)
        nf = name.font(); nf.setBold(True); nf.setPointSize(nf.pointSize() + 1)
        name.setFont(nf)
        meta = QLabel(f"v{record.version or '?'} · {record.source}"
                      + (f" · {record.author}" if record.author else ""))
        meta.setStyleSheet("color: #6c7086;")
        top.addWidget(name)
        top.addWidget(meta)
        top.addStretch(1)

        self.toggle = QCheckBox("Enabled")
        self.toggle.setChecked(record.enabled)
        self.toggle.toggled.connect(self._toggle)
        top.addWidget(self.toggle)

        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self._reload)
        top.addWidget(reload_btn)
        root.addLayout(top)

        if record.description:
            desc = QLabel(record.description)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #a6adc8;")
            root.addWidget(desc)

        if record.error:
            err = QLabel("⚠ " + record.error)
            err.setWordWrap(True)
            err.setStyleSheet("color: #f38ba8;")
            root.addWidget(err)

    def _toggle(self, checked: bool) -> None:
        self.loader.set_enabled(self.record.plugin_id, checked)
        self.on_change()

    def _reload(self) -> None:
        self.loader.reload(self.record.plugin_id)
        self.on_change()


class PluginManager(QWidget):
    def __init__(self, loader, window):
        super().__init__()
        self.loader = loader
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.setContentsMargins(24, 18, 24, 6)
        title = QLabel("Plugins")
        tf = title.font(); tf.setPointSize(tf.pointSize() + 8); tf.setBold(True)
        title.setFont(tf)
        header.addWidget(title)
        header.addStretch(1)
        reload_all = QPushButton("Reload All")
        reload_all.clicked.connect(self._reload_all)
        open_dir = QPushButton("Open Plugins Folder")
        open_dir.clicked.connect(self._open_folder)
        header.addWidget(reload_all)
        header.addWidget(open_dir)
        outer.addLayout(header)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #6c7086; padding: 0 24px;")
        outer.addWidget(self.count_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll, 1)

        self.refresh()

    def refresh(self) -> None:
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(24, 6, 24, 24)
        col.setSpacing(10)
        records = self.loader.all_records()
        for rec in records:
            col.addWidget(_PluginCard(rec, self.loader, self.refresh))
        if not records:
            empty = QLabel("No plugins found. Drop a .py file into the plugins "
                           "folder and click Reload All.")
            empty.setStyleSheet("color: #6c7086;")
            col.addWidget(empty)
        col.addStretch(1)
        self.scroll.setWidget(body)
        enabled = sum(1 for r in records if r.enabled)
        self.count_label.setText(
            f"{len(records)} installed · {enabled} enabled · "
            f"user folder: {self.loader.user_dir}")

    def _reload_all(self) -> None:
        self.window.reload_plugins()
        self.refresh()

    def _open_folder(self) -> None:
        folder = self.loader.user_dir
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(folder))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception:
            self.window.status.showMessage(f"Plugins folder: {folder}", 5000)
