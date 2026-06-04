"""Project file tree (QTreeView + QFileSystemModel) with Git status colouring."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QTreeView, QMenu, QInputDialog, QMessageBox, QFileIconProvider
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QFileInfo, QSize, QRect
from PyQt6.QtGui import QColor, QFileSystemModel, QIcon, QPixmap, QPainter, QFont, QBrush

from core.git_integration import GitStatus

# extension -> accent colour for the generated file icon
_EXT_COLORS = {
    ".py": "#3776ab", ".pyw": "#3776ab",
    ".cpp": "#9c33ff", ".cc": "#9c33ff", ".cxx": "#9c33ff", ".hpp": "#9c33ff",
    ".c": "#5599ff", ".h": "#5599ff",
    ".cs": "#178600", ".js": "#f1e05a", ".mjs": "#f1e05a", ".ts": "#3178c6",
    ".json": "#cbcb41", ".md": "#519aba", ".txt": "#9aa0a6",
    ".html": "#e34c26", ".css": "#563d7c", ".go": "#00add8", ".rs": "#dea584",
    ".rb": "#cc342d", ".php": "#777bb4", ".java": "#b07219", ".lua": "#000080",
    ".sh": "#89e051", ".yml": "#cb171e", ".yaml": "#cb171e", ".toml": "#9c4221",
    ".svg": "#ff9800", ".png": "#26a69a", ".jpg": "#26a69a", ".jpeg": "#26a69a",
    ".gitignore": "#f1502f",
}


class IconProvider(QFileIconProvider):
    """Generates small coloured per-extension file icons (no external assets)."""

    def __init__(self):
        super().__init__()
        self._cache: dict[str, QIcon] = {}

    def icon(self, info):  # type: ignore[override]
        if isinstance(info, QFileInfo):
            if info.isDir():
                return super().icon(QFileIconProvider.IconType.Folder)
            ext = ("." + info.suffix().lower()) if info.suffix() else ""
            if info.fileName().lower() == ".gitignore":
                ext = ".gitignore"
            return self._for_ext(ext, info.suffix()[:2].upper() or "•")
        return super().icon(info)

    def _for_ext(self, ext: str, label: str) -> QIcon:
        key = ext or "_"
        if key in self._cache:
            return self._cache[key]
        color = _EXT_COLORS.get(ext, "#7f8694")
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRect(1, 1, 14, 14), 4, 4)
        p.setPen(QColor("#ffffff"))
        f = QFont("Inter", 6)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRect(0, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, label[:2])
        p.end()
        icon = QIcon(pix)
        self._cache[key] = icon
        return icon


class FileTree(QTreeView):
    file_activated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.model = QFileSystemModel()
        self._icon_provider = IconProvider()
        self.setModel(self.model)
        self.git = GitStatus()
        self.root_path: str | None = None

        # show only the name column
        for col in (1, 2, 3):
            self.hideColumn(col)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(14)
        self.doubleClicked.connect(self._on_double_click)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def set_file_icons(self, enabled: bool) -> None:
        self.model.setIconProvider(self._icon_provider if enabled
                                   else QFileIconProvider())

    def set_root(self, folder: str) -> None:
        self.root_path = folder
        idx = self.model.setRootPath(folder)
        self.setRootIndex(idx)
        self.git.open(folder)
        self.refresh_git()

    def refresh_git(self) -> None:
        self.git.refresh()
        self.viewport().update()

    def _on_double_click(self, index: QModelIndex) -> None:
        path = self.model.filePath(index)
        if Path(path).is_file():
            self.file_activated.emit(path)

    # ------------------------------------------------------------ git colours
    def drawRow(self, painter, option, index):  # noqa: N802 (Qt override)
        path = self.model.filePath(index)
        status = self.git.status_for(path)
        if status == "modified":
            option.palette.setColor(option.palette.ColorRole.Text, QColor("#f9e2af"))
        elif status == "new":
            option.palette.setColor(option.palette.ColorRole.Text, QColor("#a6e3a1"))
        elif status == "deleted":
            option.palette.setColor(option.palette.ColorRole.Text, QColor("#f38ba8"))
        super().drawRow(painter, option, index)

    # ------------------------------------------------------------ context menu
    def _context_menu(self, point) -> None:
        index = self.indexAt(point)
        path = Path(self.model.filePath(index)) if index.isValid() else Path(self.root_path or ".")
        target_dir = path if path.is_dir() else path.parent

        menu = QMenu(self)
        act_new = menu.addAction("New File…")
        act_newdir = menu.addAction("New Folder…")
        menu.addSeparator()
        act_rename = menu.addAction("Rename…")
        act_delete = menu.addAction("Delete")
        chosen = menu.exec(self.viewport().mapToGlobal(point))

        if chosen == act_new:
            name, ok = QInputDialog.getText(self, "New File", "File name:")
            if ok and name:
                (target_dir / name).touch()
        elif chosen == act_newdir:
            name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
            if ok and name:
                (target_dir / name).mkdir(exist_ok=True)
        elif chosen == act_rename and index.isValid():
            name, ok = QInputDialog.getText(self, "Rename", "New name:", text=path.name)
            if ok and name:
                path.rename(path.with_name(name))
        elif chosen == act_delete and index.isValid():
            if QMessageBox.question(self, "Delete", f"Delete {path.name}?") == \
                    QMessageBox.StandardButton.Yes:
                try:
                    if path.is_dir():
                        import shutil
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                except OSError as exc:
                    QMessageBox.warning(self, "Delete failed", str(exc))
        self.refresh_git()
