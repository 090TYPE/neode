"""Welcome page shown at startup: quick actions + recent folders/files."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal


class Welcome(QWidget):
    open_folder_requested = pyqtSignal()
    new_file_requested = pyqtSignal()
    customize_requested = pyqtSignal()
    path_chosen = pyqtSignal(str)       # a recent folder
    file_chosen = pyqtSignal(str)       # a recent file

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(60, 50, 60, 50)
        col.setSpacing(8)

        title = QLabel("NeoIDE")
        tf = title.font(); tf.setPointSize(tf.pointSize() + 22); tf.setBold(True)
        title.setFont(tf)
        col.addWidget(title)
        sub = QLabel("A hackable editor for C++ and C# — built with Python + Qt6")
        sub.setStyleSheet("color: #6c7086;")
        col.addWidget(sub)
        col.addSpacing(26)

        # quick actions
        actions = QHBoxLayout()
        actions.setSpacing(10)
        open_btn = QPushButton("📂  Open Folder")
        open_btn.clicked.connect(self.open_folder_requested.emit)
        new_btn = QPushButton("📄  New File")
        new_btn.clicked.connect(self.new_file_requested.emit)
        theme_btn = QPushButton("🎨  Customize Theme")
        theme_btn.clicked.connect(self.customize_requested.emit)
        for b in (open_btn, new_btn, theme_btn):
            b.setMinimumHeight(40)
            actions.addWidget(b)
        actions.addStretch(1)
        col.addLayout(actions)
        col.addSpacing(30)

        lists = QHBoxLayout()
        lists.setSpacing(40)
        lists.addLayout(self._recent_column("Recent folders",
                                            settings.recent_folders, self.path_chosen))
        lists.addLayout(self._recent_column("Recent files",
                                            settings.recent_files, self.file_chosen))
        col.addLayout(lists)
        col.addStretch(1)

        hint = QLabel("Tip: press Ctrl+Shift+P for the command palette · "
                      "F5 to run · Ctrl+, for settings")
        hint.setStyleSheet("color: #6c7086;")
        col.addWidget(hint)

        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _recent_column(self, heading: str, items: list[str], signal) -> QVBoxLayout:
        box = QVBoxLayout()
        label = QLabel(heading)
        f = label.font(); f.setBold(True)
        label.setFont(f)
        box.addWidget(label)
        listw = QListWidget()
        listw.setMaximumWidth(380)
        existing = [p for p in items if Path(p).exists()]
        if not existing:
            listw.addItem("Nothing yet")
            listw.setEnabled(False)
        else:
            for path in existing[:12]:
                item = QListWidgetItem(Path(path).name + "   ")
                item.setToolTip(path)
                item.setData(Qt.ItemDataRole.UserRole, path)
                listw.addItem(item)
            listw.itemActivated.connect(
                lambda it: signal.emit(it.data(Qt.ItemDataRole.UserRole)))
            listw.itemClicked.connect(
                lambda it: signal.emit(it.data(Qt.ItemDataRole.UserRole)))
        box.addWidget(listw)
        return box
