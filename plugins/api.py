"""Plugin API — the surface plugins use to touch the IDE.

A plugin receives one ``PluginAPI`` instance and reaches the whole IDE through
small facades, so it never imports concrete widget classes:

    api.editor      — read/modify the active editor
    api.terminal    — run shell commands
    api.ui          — commands, notifications, side panels, tabs
    api.statusbar   — add status-bar widgets / text
    api.git         — git status + commit
    api.events      — subscribe to lifecycle events (see EVENTS)
    api.storage     — per-plugin persisted key/value store
    api.lang        — register extra run commands / themes

Lifecycle events (api.events.on(name, cb)):
    app_ready()                  once, after startup
    folder_opened(path)
    file_opened(path)
    before_save(editor, path)    may modify editor text before it is written
    file_saved(path)
    file_closed(path)
    theme_changed(theme)
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from PyQt6.QtWidgets import QLabel

EVENTS = (
    "app_ready", "folder_opened", "file_opened", "before_save", "file_saved",
    "file_closed", "theme_changed",
)


class EventBus:
    def __init__(self):
        self._subs: dict[str, list] = defaultdict(list)

    def on(self, event: str, callback) -> None:
        self._subs[event].append(callback)

    def off(self, event: str, callback) -> None:
        if callback in self._subs.get(event, []):
            self._subs[event].remove(callback)

    def emit(self, event: str, *args, **kwargs) -> None:
        for cb in list(self._subs.get(event, [])):
            try:
                cb(*args, **kwargs)
            except Exception:
                pass


class _EditorFacade:
    def __init__(self, window):
        self._w = window

    def _ed(self):
        return self._w.tabs.current_editor()

    def get_text(self) -> str:
        ed = self._ed()
        return ed.text() if ed else ""

    def set_text(self, text: str) -> None:
        ed = self._ed()
        if ed:
            ed.setText(text)

    def get_selection(self) -> str:
        ed = self._ed()
        return ed.selectedText() if ed else ""

    def replace_selection(self, text: str) -> None:
        ed = self._ed()
        if ed and ed.hasSelectedText():
            ed.replaceSelectedText(text)

    def insert_text(self, text: str) -> None:
        ed = self._ed()
        if ed:
            line, col = ed.getCursorPosition()
            ed.insertAt(text, line, col)

    def get_cursor_position(self) -> tuple[int, int]:
        ed = self._ed()
        return ed.getCursorPosition() if ed else (0, 0)

    def current_path(self) -> str | None:
        ed = self._ed()
        return ed.property("path") if ed else None

    def current_language(self) -> str:
        ed = self._ed()
        return ed.language if ed else "Plain Text"


class _TerminalFacade:
    def __init__(self, window):
        self._w = window

    def run(self, command: str) -> None:
        self._w._show_terminal()
        self._w.terminal.run_command(command)

    def run_file(self, path: str) -> None:
        self._w._show_terminal()
        self._w.terminal.run_file(path)


class _UiFacade:
    def __init__(self, window):
        self._w = window

    def register_command(self, title: str, callback, shortcut: str | None = None) -> None:
        self._w.palette.register(title, shortcut, callback)

    # kept for backwards compatibility
    add_menu_item = register_command

    def show_notification(self, text: str, msec: int = 3000) -> None:
        self._w.status.showMessage(text, msec)

    def add_panel(self, title: str, widget) -> None:
        """Add a widget as a new tab in the left side panel."""
        self._w.side_tabs.addTab(widget, title)

    def add_tab(self, title: str, widget) -> None:
        """Add a widget as a main editor-area tab."""
        idx = self._w.tabs.addTab(widget, title)
        self._w.tabs.setCurrentIndex(idx)

    def open_file(self, path: str) -> None:
        self._w.tabs.open_file(path)


class _StatusBarFacade:
    def __init__(self, window):
        self._w = window
        self._widgets: list = []

    def add_text(self, text: str = "") -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #a6adc8; padding: 0 6px;")
        self._w.status.addPermanentWidget(label)
        self._widgets.append(label)
        return label

    def add_widget(self, widget) -> None:
        self._w.status.addPermanentWidget(widget)
        self._widgets.append(widget)

    def remove(self, widget) -> None:
        self._w.status.removeWidget(widget)
        if widget in self._widgets:
            self._widgets.remove(widget)


class _GitFacade:
    def __init__(self, window):
        self._w = window

    @property
    def status(self):
        return self._w.file_tree.git

    def refresh(self) -> None:
        self._w.file_tree.refresh_git()


class _LangFacade:
    """Register extra run commands and themes at runtime."""
    def __init__(self, window):
        self._w = window

    def register_runner(self, ext: str, command_template: str) -> None:
        from core import runners
        if not ext.startswith("."):
            ext = "." + ext
        runners.EXTRA_RUNNERS[ext.lower()] = command_template
        runners.RUNNABLE.add(ext.lower())

    def register_theme(self, theme_dict: dict) -> str:
        from core.theme import Theme
        theme = Theme.from_dict(theme_dict)
        theme_id = self._w.themes.slugify(theme.name)
        self._w.themes.themes[theme_id] = theme
        return theme_id


class _Storage:
    """Per-plugin persisted key/value store (JSON in the plugin data dir)."""
    def __init__(self, path: Path):
        self._path = path
        self._data: dict = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._flush()

    def _flush(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass


class PluginAPI:
    def __init__(self, window, data_dir: Path | None = None):
        self.window = window
        self.settings = window.settings
        self.editor = _EditorFacade(window)
        self.terminal = _TerminalFacade(window)
        self.ui = _UiFacade(window)
        self.statusbar = _StatusBarFacade(window)
        self.git = _GitFacade(window)
        self.lang = _LangFacade(window)
        self.events = EventBus()
        self._data_dir = data_dir or (Path.home() / ".neode" / "plugin_data")

    def storage(self, plugin_name: str) -> _Storage:
        slug = "".join(c if c.isalnum() else "_" for c in plugin_name.lower())
        return _Storage(self._data_dir / f"{slug}.json")
