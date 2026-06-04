"""Tabbed container of CodeEditor instances with open/save/dirty tracking."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QTabWidget, QFileDialog, QMessageBox, QMenu
from PyQt6.QtCore import pyqtSignal, Qt

from core.editor import CodeEditor


class EditorTabs(QTabWidget):
    # emitted with (line, col, language) whenever the active editor cursor moves
    cursor_moved = pyqtSignal(int, int, str)
    file_opened = pyqtSignal(str)
    file_saved = pyqtSignal(str)
    file_closed = pyqtSignal(str)

    def __init__(self, theme=None, settings=None):
        super().__init__()
        self.theme = theme
        self.settings = settings
        # optional callback(editor, path) run just before a file is written
        self.before_save_hook = None
        # recently closed file paths (most recent last)
        self._closed_stack: list[str] = []
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.tabCloseRequested.connect(self.close_tab)
        # path -> editor, to avoid opening the same file twice
        self._by_path: dict[str, CodeEditor] = {}
        self.editor_bg_alpha = 255  # propagated to new editors for wallpaper mode
        self._pinned: set = set()   # ids of pinned editor widgets
        self.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._tab_menu)

    # ------------------------------------------------------------- accessors
    def current_editor(self) -> CodeEditor | None:
        w = self.currentWidget()
        return w if isinstance(w, CodeEditor) else None

    def _new_editor(self) -> CodeEditor:
        fam = self.settings.font_family if self.settings else "JetBrains Mono"
        size = self.settings.font_size if self.settings else 13
        editor = CodeEditor(self.theme, font_family=fam, font_size=size)
        editor.set_translucent(self.editor_bg_alpha)
        if self.settings is not None:
            editor.apply_preferences(self.settings)
        if self.theme is not None:
            editor.apply_theme(self.theme)
        editor.cursorPositionChanged.connect(
            lambda line, col, e=editor: self.cursor_moved.emit(line, col, e.language)
        )
        editor.modificationChanged.connect(
            lambda changed, e=editor: self._mark_dirty(e, changed)
        )
        return editor

    # ------------------------------------------------------------- file ops
    def new_file(self) -> None:
        editor = self._new_editor()
        idx = self.addTab(editor, "untitled")
        self.setCurrentIndex(idx)
        editor.setProperty("path", None)

    def open_file(self, path: str | None = None) -> None:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open File")
            if not path:
                return
        path = str(Path(path).resolve())

        if path in self._by_path:
            self.setCurrentWidget(self._by_path[path])
            return

        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            QMessageBox.warning(self, "Open failed", str(exc))
            return

        editor = self._new_editor()
        editor.set_language_for(path)
        editor.setText(text)
        editor.setModified(False)
        editor.setProperty("path", path)
        if self.theme is not None:
            editor.apply_theme(self.theme)

        idx = self.addTab(editor, Path(path).name)
        self.setTabToolTip(idx, path)
        self.setCurrentIndex(idx)
        self._by_path[path] = editor
        self.file_opened.emit(path)

    def save_current(self) -> bool:
        editor = self.current_editor()
        if editor is None:
            return False
        path = editor.property("path")
        if not path:
            return self.save_current_as()
        return self._write(editor, path)

    def save_current_as(self) -> bool:
        editor = self.current_editor()
        if editor is None:
            return False
        path, _ = QFileDialog.getSaveFileName(self, "Save As")
        if not path:
            return False
        return self._write(editor, str(Path(path).resolve()))

    def _write(self, editor: CodeEditor, path: str) -> bool:
        # let plugins inspect/modify the buffer right before it is written
        if self.before_save_hook is not None:
            try:
                self.before_save_hook(editor, path)
            except Exception:
                pass
        try:
            Path(path).write_text(editor.text(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False
        old = editor.property("path")
        if old and old in self._by_path:
            del self._by_path[old]
        editor.setProperty("path", path)
        editor.set_language_for(path)
        if self.theme is not None:
            editor.apply_theme(self.theme)
        editor.setModified(False)
        self._by_path[path] = editor
        idx = self.indexOf(editor)
        self.setTabText(idx, Path(path).name)
        self.setTabToolTip(idx, path)
        self.file_saved.emit(path)
        return True

    # ------------------------------------------------------------- dirty/close
    def _mark_dirty(self, editor: CodeEditor, dirty: bool) -> None:
        idx = self.indexOf(editor)
        if idx < 0:
            return
        self._relabel(editor)

    def close_tab(self, index: int) -> None:
        editor = self.widget(index)
        if isinstance(editor, CodeEditor) and editor.isModified():
            choice = QMessageBox.question(
                self,
                "Unsaved changes",
                "Save changes before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.Save:
                self.setCurrentIndex(index)
                if not self.save_current():
                    return
        path = editor.property("path") if isinstance(editor, CodeEditor) else None
        if path and path in self._by_path:
            del self._by_path[path]
        self._pinned.discard(id(editor))
        self.removeTab(index)
        if path:
            self._closed_stack.append(path)
            self._closed_stack = self._closed_stack[-25:]
            self.file_closed.emit(path)

    def reopen_last_closed(self) -> bool:
        while self._closed_stack:
            path = self._closed_stack.pop()
            if Path(path).is_file():
                self.open_file(path)
                return True
        return False

    # ------------------------------------------------------------- pinning
    def _tab_menu(self, point) -> None:
        index = self.tabBar().tabAt(point)
        if index < 0:
            return
        widget = self.widget(index)
        pinned = id(widget) in self._pinned
        menu = QMenu(self)
        act_pin = menu.addAction("Unpin Tab" if pinned else "Pin Tab")
        act_close = menu.addAction("Close")
        act_others = menu.addAction("Close Others")
        chosen = menu.exec(self.tabBar().mapToGlobal(point))
        if chosen == act_pin:
            self.toggle_pin(index)
        elif chosen == act_close:
            self.close_tab(index)
        elif chosen == act_others:
            self._close_others(index)

    def toggle_pin(self, index: int) -> None:
        widget = self.widget(index)
        if widget is None:
            return
        if id(widget) in self._pinned:
            self._pinned.discard(id(widget))
        else:
            self._pinned.add(id(widget))
            self.tabBar().moveTab(index, 0)
            index = 0
        self._relabel(self.widget(index))

    def _relabel(self, widget) -> None:
        idx = self.indexOf(widget)
        if idx < 0:
            return
        path = widget.property("path") if isinstance(widget, CodeEditor) else None
        base = Path(path).name if path else self.tabText(idx).lstrip("📌• ").strip()
        dirty = isinstance(widget, CodeEditor) and widget.isModified()
        prefix = "📌 " if id(widget) in self._pinned else ""
        prefix += "• " if dirty else ""
        self.setTabText(idx, prefix + base)

    def _close_others(self, keep_index: int) -> None:
        keep = self.widget(keep_index)
        for i in reversed(range(self.count())):
            w = self.widget(i)
            if w is keep or id(w) in self._pinned:
                continue
            self.close_tab(i)

    def apply_theme(self, theme) -> None:
        self.theme = theme
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, CodeEditor):
                w.apply_theme(theme)

    def apply_preferences(self) -> None:
        if self.settings is None:
            return
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, CodeEditor):
                w.apply_preferences(self.settings)

    def set_editor_translucency(self, alpha: int) -> None:
        """Set paper alpha on all editors (wallpaper mode) and re-theme them."""
        self.editor_bg_alpha = alpha
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, CodeEditor):
                w.set_translucent(alpha)
                if self.theme is not None:
                    w.apply_theme(self.theme)
