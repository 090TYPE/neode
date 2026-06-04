"""NeoIDE main window: frameless shell hosting titlebar, side panel (files +
outline), editor tabs with a find bar, terminal, status bar, command palette,
quick-open, settings and the plugin system."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFileDialog,
    QInputDialog, QTabWidget, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence

from core.editor_tabs import EditorTabs
from core.file_tree import FileTree
from ui.terminal_tabs import TerminalTabs
from core.lsp_client import LspManager
from core import git_diff
from core import runners
from ui.titlebar import TitleBar
from ui.statusbar import StatusBar
from ui.command_palette import CommandPalette
from ui.find_bar import FindBar
from ui.quick_open import QuickOpen
from ui.settings_dialog import SettingsDialog
from ui.settings_page import SettingsPage
from ui.symbols_panel import SymbolsPanel
from ui.theme_editor import ThemeEditor
from ui.backdrop import Backdrop
from ui.toolbar import ActionToolBar
from ui.find_in_files import FindInFiles
from ui.markdown_preview import MarkdownPreview
from ui.sticky_scroll import StickyScroll
from ui.breadcrumbs import Breadcrumbs
from ui.minimap import Minimap
from ui.welcome import Welcome
from plugins.loader import PluginLoader
from plugins.api import PluginAPI


class MainWindow(QMainWindow):
    def __init__(self, app, settings, themes, root: Path):
        super().__init__()
        self.app = app
        self.settings = settings
        self.themes = themes
        self.root = root
        self.lsp: LspManager | None = None
        self._connected_clients: set = set()
        self._doc_versions: dict[str, int] = {}

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(1280, 800)

        # ---- central layout: backdrop hosts titlebar + splitters ----
        container = Backdrop()
        self.backdrop = container
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.titlebar = TitleBar(self)
        outer.addWidget(self.titlebar)

        self.toolbar = ActionToolBar({
            "run": self.run_current,
            "stop": self.stop_run,
            "new": self.act_new_file,
            "open_folder": self.open_folder_dialog,
            "search": self.show_find_in_files,
            "packages": self.open_package_manager,
            "palette": self.palette_popup,
            "settings": self.open_settings,
        })
        outer.addWidget(self.toolbar)

        self.tabs = EditorTabs(theme=themes.current, settings=settings)
        self.tabs2: EditorTabs | None = None      # second split pane (lazy)
        self._active_pane = self.tabs
        self.file_tree = FileTree()
        self.file_tree.set_file_icons(settings.file_icons)
        self.terminal = TerminalTabs()
        self.symbols = SymbolsPanel()
        self.find_in_files = FindInFiles()

        # left side panel: Files + Outline + Search (+ plugin tabs e.g. Git)
        self.side_tabs = QTabWidget()
        self.side_tabs.setDocumentMode(True)
        self.side_tabs.addTab(self._build_files_tab(), "Files")
        self.side_tabs.addTab(self.symbols, "Outline")
        self.side_tabs.addTab(self.find_in_files, "Search")
        from ui.ai_assistant import AiAssistant
        self.ai_assistant = AiAssistant(self)
        self.side_tabs.addTab(self.ai_assistant, "AI")

        # find bar + breadcrumbs sit above the editor tabs
        self.find_bar = FindBar(self.active_editor)
        self.breadcrumbs = Breadcrumbs()
        self.breadcrumbs.symbol_clicked.connect(self._goto_symbol_line)
        self.minimap = Minimap(self.active_editor)
        self.minimap.set_enabled(settings.minimap)

        # horizontal splitter holds the editor pane(s) and the minimap
        self.editor_split = QSplitter(Qt.Orientation.Horizontal)
        self.editor_split.addWidget(self.tabs)
        self.editor_split.addWidget(self.minimap)
        self.editor_split.setStretchFactor(0, 1)
        self.editor_split.setStretchFactor(1, 0)

        editor_area = QWidget()
        ea_layout = QVBoxLayout(editor_area)
        ea_layout.setContentsMargins(0, 0, 0, 0)
        ea_layout.setSpacing(0)
        ea_layout.addWidget(self.find_bar)
        ea_layout.addWidget(self.breadcrumbs)
        ea_layout.addWidget(self.editor_split, 1)

        # editor area + terminal stacked vertically
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(editor_area)
        right.addWidget(self.terminal)
        right.setSizes([600, 180])
        self.terminal_splitter = right

        # side panel | (editor/terminal)
        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(self.side_tabs)
        main_split.addWidget(right)
        main_split.setSizes([240, 1040])
        outer.addWidget(main_split, 1)

        self.setCentralWidget(container)

        self.status = StatusBar()
        self.setStatusBar(self.status)

        # ---- dialogs ----
        self.palette = CommandPalette(self)
        self.quick_open = QuickOpen(self)
        self.quick_open.file_chosen.connect(lambda p: self.active_tabs().open_file(p))

        # ---- autosave + symbol-refresh debounce ----
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave_tick)
        self._apply_autosave_setting()

        self._symbol_timer = QTimer(self)
        self._symbol_timer.setSingleShot(True)
        self._symbol_timer.setInterval(400)
        self._symbol_timer.timeout.connect(self._refresh_symbols)

        self._git_timer = QTimer(self)
        self._git_timer.setSingleShot(True)
        self._git_timer.setInterval(500)
        self._git_timer.timeout.connect(self._refresh_git_signals)
        self._blame_map: dict[int, tuple] = {}
        self._sticky = StickyScroll(self.active_editor)
        self._sticky.set_enabled(settings.sticky_scroll)
        app.focusChanged.connect(self._on_focus_changed)

        # ---- signals ----
        self.file_tree.file_activated.connect(lambda p: self.active_tabs().open_file(p))
        self.tabs.cursor_moved.connect(self._on_cursor)
        self.tabs.file_opened.connect(self._on_file_opened)
        self.tabs.file_saved.connect(self._on_file_saved)
        self.tabs.currentChanged.connect(lambda _i: self._refresh_symbols())
        self.tabs.currentChanged.connect(lambda _i: self._refresh_git_signals())
        self.terminal.error_clicked.connect(self._jump_to_error)
        self.terminal.running_changed.connect(self.toolbar.set_running)
        self.terminal.running_changed.connect(self._on_run_state)
        self.terminal.diagnostic_found.connect(self._on_compiler_diagnostic)
        self.symbols.symbol_activated.connect(self._goto_symbol_line)
        self.find_in_files.result_activated.connect(self._jump_to_error)
        self._run_diags: dict[str, list] = {}

        # ---- commands / shortcuts / plugins ----
        self._register_commands()
        self._bind_shortcuts()

        self.api = PluginAPI(self)
        self.plugins = PluginLoader(root / "plugins", self.api)
        # plugin lifecycle hooks
        self.tabs.before_save_hook = \
            lambda editor, path: self.api.events.emit("before_save", editor, path)
        self.tabs.file_closed.connect(
            lambda path: self.api.events.emit("file_closed", path))
        self._plugin_manager_page = None
        self._packages_page = None
        self.plugins.discover()

        themes.on_change(self._on_theme_changed)
        self._settings_page = None
        self._zen = False
        self._zen_state = None
        runners.PYTHON_OVERRIDE = settings.python_path
        self.apply_background()
        if not self.tabs.count():
            self.show_welcome()
        self.api.events.emit("app_ready")

    # ------------------------------------------------------------ files tab
    def _build_files_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 4)
        self.folder_label = QLabel("No folder open")
        self.folder_label.setStyleSheet("color: #6c7086;")
        open_btn = QPushButton("Open Folder…")
        open_btn.clicked.connect(self.open_folder_dialog)
        bar.addWidget(self.folder_label, 1)
        bar.addWidget(open_btn)
        layout.addLayout(bar)

        layout.addWidget(self.file_tree, 1)
        return wrapper

    # ------------------------------------------------------------ commands
    def _register_commands(self) -> None:
        reg = self.palette.register
        reg("New File", "Ctrl+N", self.act_new_file)
        reg("Open File…", "Ctrl+O", self.act_open_file)
        reg("Open Folder…", "Ctrl+K Ctrl+O", self.open_folder_dialog)
        reg("Quick Open…", "Ctrl+P", self.show_quick_open)
        reg("Save", "Ctrl+S", self.act_save)
        reg("Save As…", "Ctrl+Shift+S", self.act_save_as)
        reg("Split Editor", "Ctrl+\\", self.toggle_split)
        reg("Find…", "Ctrl+F", self.find_bar.show_find)
        reg("Replace…", "Ctrl+H", self.find_bar.show_replace)
        reg("Go to Line…", "Ctrl+G", self.goto_line)
        reg("Duplicate Line", "Ctrl+Shift+D", self._duplicate_line)
        reg("Move Line Up", "Alt+Up", self._move_line_up)
        reg("Move Line Down", "Alt+Down", self._move_line_down)
        reg("Add Next Occurrence (multi-cursor)", "Ctrl+D", self._add_cursor)
        reg("Toggle Comment", "Ctrl+/", self._toggle_comment)
        reg("Insert Snippet…", "Ctrl+J", self.insert_snippet)
        reg("Toggle Word Wrap", "Alt+Z", self._toggle_wrap)
        reg("Zoom In", "Ctrl+=", self._zoom_in)
        reg("Zoom Out", "Ctrl+-", self._zoom_out)
        reg("Reset Zoom", "Ctrl+0", self._zoom_reset)
        reg("Show Outline", "Ctrl+Shift+O", self.show_outline)
        reg("Find in Files…", "Ctrl+Shift+F", self.show_find_in_files)
        reg("Open Markdown Preview", "Ctrl+Shift+V", self.open_markdown_preview)
        reg("Run Current File", "F5", self.run_current)
        reg("Stop Running", "Shift+F5", self.stop_run)
        reg("Run Command…", None, self.run_command_prompt)
        reg("Install Package…", None, self.quick_install_package)
        reg("Manage Packages…", None, self.open_package_manager)
        reg("REST Client", None, self.open_rest_client)
        reg("Git Graph", None, self.open_git_graph)
        reg("AI: Explain Selection", None, lambda: self._ai_action("explain"))
        reg("AI: Refactor Selection", None, lambda: self._ai_action("refactor"))
        reg("Clear Terminal", None, self.terminal.clear)
        reg("New Terminal", "Ctrl+Shift+`", lambda: (self._show_terminal(), self.terminal.add_terminal()))
        reg("Toggle Terminal", "Ctrl+`", self.toggle_terminal)
        reg("Toggle Zen Mode", "Ctrl+K Z", self.toggle_zen)
        reg("Toggle Fullscreen", "F11", self.toggle_fullscreen)
        reg("Open Recent Folder…", None, self.open_recent_folder)
        reg("Open Recent File…", None, self.open_recent_file)
        reg("Welcome", None, self.show_welcome)
        reg("Manage Plugins…", None, self.open_plugin_manager)
        reg("Reopen Closed Tab", "Ctrl+Shift+T", self.reopen_closed_tab)
        reg("Change Theme…", None, self.choose_theme)
        reg("Customize Theme…", "Ctrl+K Ctrl+T", self.open_theme_editor)
        reg("Settings", "Ctrl+,", self.open_settings)
        reg("Go to Definition", "F12", self.goto_definition)
        reg("Reload Plugins", None, self.reload_plugins)

    def _bind_shortcuts(self) -> None:
        binds = {
            "Ctrl+N": self.act_new_file,
            "Ctrl+O": self.act_open_file,
            "Ctrl+K, Ctrl+O": self.open_folder_dialog,
            "Ctrl+P": self.show_quick_open,
            "Ctrl+S": self.act_save,
            "Ctrl+Shift+S": self.act_save_as,
            "Ctrl+\\": self.toggle_split,
            "Ctrl+F": self.find_bar.show_find,
            "Ctrl+H": self.find_bar.show_replace,
            "F3": self.find_bar.find_next,
            "Shift+F3": self.find_bar.find_prev,
            "Ctrl+G": self.goto_line,
            "Ctrl+J": self.insert_snippet,
            "Ctrl+Shift+D": self._duplicate_line,
            "Alt+Up": self._move_line_up,
            "Alt+Down": self._move_line_down,
            "Ctrl+D": self._add_cursor,
            "F11": self.toggle_fullscreen,
            "Ctrl+/": self._toggle_comment,
            "Alt+Z": self._toggle_wrap,
            "Ctrl+=": self._zoom_in,
            "Ctrl++": self._zoom_in,
            "Ctrl+-": self._zoom_out,
            "Ctrl+0": self._zoom_reset,
            "Ctrl+Shift+O": self.show_outline,
            "F5": self.run_current,
            "Shift+F5": self.stop_run,
            "Ctrl+Shift+F": self.show_find_in_files,
            "Ctrl+Shift+V": self.open_markdown_preview,
            "Ctrl+`": self.toggle_terminal,
            "Ctrl+Shift+P": self.palette.popup,
            "Ctrl+,": self.open_settings,
            "Ctrl+K, Z": self.toggle_zen,
            "Ctrl+Shift+T": self.reopen_closed_tab,
            "Ctrl+K, Ctrl+T": self.open_theme_editor,
            "F12": self.goto_definition,
            "Ctrl+Space": self.request_completion,
            "Ctrl+W": self.act_close_tab,
        }
        for seq, slot in binds.items():
            QShortcut(QKeySequence(seq), self, activated=slot)

    # ------------------------------------------------------------ actions
    def open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self.open_folder(folder)

    def open_folder(self, folder: str) -> None:
        self.file_tree.set_root(folder)
        self.terminal.set_workdir(folder)
        self.settings.remember_folder(folder)
        self.status.set_branch(self.file_tree.git.branch)
        self.titlebar.set_title(f"NeoIDE — {Path(folder).name}")
        self.folder_label.setText(Path(folder).name)
        self.folder_label.setToolTip(folder)
        self.side_tabs.setCurrentIndex(0)
        self.lsp = LspManager(folder, self.settings)
        self.quick_open.index(folder)
        self.find_in_files.set_root(folder)
        self.breadcrumbs.set_root(folder)
        self.api.events.emit("folder_opened", folder)

    def open_initial_folder(self) -> None:
        """Auto-open the most recent still-existing folder on startup."""
        for folder in self.settings.recent_folders:
            if Path(folder).is_dir():
                self.open_folder(folder)
                return

    def show_quick_open(self) -> None:
        if not self.quick_open._files and self.file_tree.root_path:
            self.quick_open.index(self.file_tree.root_path)
        self.quick_open.popup()

    def goto_line(self) -> None:
        editor = self.active_editor()
        if editor is None:
            return
        total = editor.lines()
        line, ok = QInputDialog.getInt(
            self, "Go to Line", f"Line (1–{total}):", 1, 1, total
        )
        if ok:
            editor.goto_line(line - 1, 0)

    def show_outline(self) -> None:
        self._refresh_symbols()
        self.side_tabs.setCurrentWidget(self.symbols)

    def show_find_in_files(self) -> None:
        self.side_tabs.setCurrentWidget(self.find_in_files)
        self.find_in_files.focus()

    def open_markdown_preview(self) -> None:
        editor = self.active_editor()
        if editor is None:
            return
        path = editor.property("path")
        title = Path(path).name if path else "untitled"
        if not (path and path.lower().endswith((".md", ".markdown"))):
            self.status.showMessage("Open a Markdown (.md) file first", 2500)
            return
        preview = MarkdownPreview(editor, title)
        idx = self.tabs.addTab(preview, f"◳ {title}")
        self.tabs.setCurrentIndex(idx)

    # ------------------------------------------------------------ panes/split
    def active_tabs(self):
        return self._active_pane if self._active_pane is not None else self.tabs

    def active_editor(self):
        return self.active_tabs().current_editor()

    def act_new_file(self) -> None:
        self.active_tabs().new_file()

    def act_open_file(self) -> None:
        self.active_tabs().open_file()

    def act_save(self) -> bool:
        return self.active_tabs().save_current()

    def act_save_as(self) -> bool:
        return self.active_tabs().save_current_as()

    def act_close_tab(self) -> None:
        t = self.active_tabs()
        t.close_tab(t.currentIndex())

    def _on_focus_changed(self, _old, new) -> None:
        if new is None:
            return
        w = new
        while w is not None:
            if w is self.tabs:
                self._active_pane = self.tabs
                return
            if self.tabs2 is not None and w is self.tabs2:
                self._active_pane = self.tabs2
                return
            w = w.parent()

    def toggle_split(self) -> None:
        if self.tabs2 is None:
            self.tabs2 = EditorTabs(theme=self.themes.current, settings=self.settings)
            self._wire_pane(self.tabs2)
            self.editor_split.insertWidget(1, self.tabs2)
            self.editor_split.setStretchFactor(1, 1)
            # move the current file into the new pane if possible
            ed = self.active_editor()
            path = ed.property("path") if ed else None
            if path:
                self.tabs2.open_file(path)
            else:
                self.tabs2.new_file()
            self._active_pane = self.tabs2
            self.status.showMessage("Editor split — Toggle Split again to close", 2500)
        else:
            self.tabs2.setParent(None)
            self.tabs2.deleteLater()
            self.tabs2 = None
            self._active_pane = self.tabs

    def _wire_pane(self, pane) -> None:
        pane.cursor_moved.connect(self._on_cursor)
        pane.file_opened.connect(self._on_file_opened)
        pane.file_saved.connect(self._on_file_saved)
        pane.currentChanged.connect(lambda _i: self._refresh_symbols())
        pane.before_save_hook = \
            lambda editor, path: self.api.events.emit("before_save", editor, path)
        pane.file_closed.connect(
            lambda path: self.api.events.emit("file_closed", path))

    def palette_popup(self) -> None:
        self.palette.popup()

    def reopen_closed_tab(self) -> None:
        if not self.tabs.reopen_last_closed():
            self.status.showMessage("No recently closed files", 2000)

    def stop_run(self) -> None:
        self.terminal.stop()

    def run_command_prompt(self) -> None:
        cmd, ok = QInputDialog.getText(self, "Run Command", "Command:")
        if ok and cmd.strip():
            self._show_terminal()
            self.terminal.run_command(cmd.strip())

    def open_package_manager(self) -> None:
        from ui.package_manager import PackageManager
        if self._packages_page is not None:
            idx = self.tabs.indexOf(self._packages_page)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)
                self._packages_page.auto_select()
                return
        page = PackageManager(self)
        self._packages_page = page
        idx = self.tabs.addTab(page, "📦 Packages")
        self.tabs.setCurrentIndex(idx)

    def open_rest_client(self) -> None:
        from ui.rest_client import RestClient
        page = getattr(self, "_rest_page", None)
        if page is not None and self.tabs.indexOf(page) >= 0:
            self.tabs.setCurrentWidget(page)
            return
        self._rest_page = RestClient()
        idx = self.tabs.addTab(self._rest_page, "🌐 REST")
        self.tabs.setCurrentIndex(idx)

    def open_git_graph(self) -> None:
        from ui.git_graph import GitGraph
        page = getattr(self, "_gitgraph_page", None)
        if page is not None and self.tabs.indexOf(page) >= 0:
            self.tabs.setCurrentWidget(page)
            page.refresh()
            return
        self._gitgraph_page = GitGraph(self)
        idx = self.tabs.addTab(self._gitgraph_page, "⎇ Git Graph")
        self.tabs.setCurrentIndex(idx)

    def _ai_action(self, kind: str) -> None:
        self.side_tabs.setCurrentWidget(self.ai_assistant)
        if kind == "explain":
            self.ai_assistant._on_code("Explain this code clearly:")
        else:
            self.ai_assistant._on_code(
                "Refactor this code for clarity; return only the improved code:")

    def quick_install_package(self) -> None:
        from core import packages
        root = self.file_tree.root_path
        mid = packages.detect(root)
        name, ok = QInputDialog.getText(
            self, "Install Package",
            f"Package to install with {packages.MANAGERS[mid].label}:")
        if ok and name.strip():
            cmd = packages.build(mid, "install", root, name.strip())
            if cmd:
                if root:
                    self.terminal.set_workdir(root)
                self._show_terminal()
                self.terminal.run_command(cmd)

    def run_current(self) -> None:
        editor = self.active_editor()
        if editor is None:
            self.status.showMessage("Nothing to run", 2000)
            return
        path = editor.property("path")
        if not path or editor.isModified():
            if not self.act_save():
                return
            path = editor.property("path")
        if path:
            self._show_terminal()
            self.terminal.run_file(path)

    def toggle_terminal(self) -> None:
        sizes = self.terminal_splitter.sizes()
        if sizes[-1] > 0:
            self._stored_term_size = sizes[-1]
            self.terminal_splitter.setSizes([sum(sizes), 0])
        else:
            self._show_terminal()

    def _show_terminal(self) -> None:
        sizes = self.terminal_splitter.sizes()
        if sizes[-1] == 0:
            total = sum(sizes)
            self.terminal_splitter.setSizes([total - 200, 200])

    def choose_theme(self) -> None:
        names = self.themes.names()
        if not names:
            return
        current = self.settings.theme if self.settings.theme in names else names[0]
        name, ok = QInputDialog.getItem(
            self, "Change Theme", "Theme:", names, names.index(current), False
        )
        if ok and name:
            self.themes.apply(name, self.app, self)
            self.settings.theme = name
            self.settings.save()

    def open_theme_editor(self) -> None:
        editor = ThemeEditor(self.themes, self.settings, self.app, self, self)
        editor.exec()

    # ------------------------------------------------------------ background
    def apply_background(self) -> None:
        s = self.settings
        # self-heal: a path that no longer exists would silently show nothing
        if s.bg_image and not Path(s.bg_image).exists():
            self.status.showMessage(
                f"Background image not found — cleared: {s.bg_image}", 4000)
            s.bg_image = ""
            s.save()
        active = bool(s.bg_image) and Path(s.bg_image).exists()
        panel_alpha = max(0.4, min(1.0, s.panel_opacity / 100))
        self.themes.backdrop_active = active
        self.themes.panel_alpha = panel_alpha

        base = "#1e1e2e"
        if self.themes.current is not None:
            base = self.themes.current.ui.get("background", base)
        self.backdrop.set_base_color(base)
        if active:
            self.backdrop.set_image(s.bg_image, s.bg_mode, s.bg_opacity)
        else:
            self.backdrop.clear_image()

        # the code area is made noticeably more see-through than the panels so
        # the wallpaper reads behind code as strongly as behind the settings panel
        if active and s.editor_translucent:
            code_alpha = int(max(0.30, panel_alpha - 0.30) * 255)
        else:
            code_alpha = 255
        for pane in (self.tabs, self.tabs2):
            if pane is not None:
                pane.set_editor_translucency(code_alpha)

        if self.themes.current is not None:
            self.themes.apply_object(self.themes.current, self.app, self)
        self.backdrop.update()

    def open_settings_tab(self) -> None:
        # reuse the page if it's already open
        if self._settings_page is not None:
            idx = self.tabs.indexOf(self._settings_page)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)
                return
        page = SettingsPage(self.settings, self.themes.names(), self)
        page.saved.connect(self._on_settings_applied)
        page.edit_theme_requested.connect(self.open_theme_editor)
        page.background_changed.connect(self.apply_background)
        self._settings_page = page
        idx = self.tabs.addTab(page, "⚙  Settings")
        self.tabs.setTabToolTip(idx, "NeoIDE settings")
        self.tabs.setCurrentIndex(idx)

    def open_settings(self) -> None:
        self.open_settings_tab()

    def _on_settings_applied(self) -> None:
        # font lives in the theme; push the chosen size/family into it
        if self.themes.current is not None:
            self.themes.current.font["size"] = self.settings.font_size
            self.themes.current.font["family"] = self.settings.font_family
        self.themes.apply(self.settings.theme, self.app, self)
        self.tabs.apply_preferences()
        if self.tabs2 is not None:
            self.tabs2.apply_preferences()
        self.file_tree.set_file_icons(self.settings.file_icons)
        self._sticky.set_enabled(self.settings.sticky_scroll)
        self.minimap.set_enabled(self.settings.minimap)
        self._update_breadcrumbs()
        runners.PYTHON_OVERRIDE = self.settings.python_path
        self.apply_background()
        self._apply_autosave_setting()
        self._refresh_git_signals()
        self.status.showMessage("Settings applied", 2000)

    # ------------------------------------------------------------ editor verbs
    def _toggle_comment(self) -> None:
        editor = self.active_editor()
        if editor:
            editor.toggle_comment()

    def _toggle_wrap(self) -> None:
        editor = self.active_editor()
        if editor:
            on = editor.toggle_word_wrap()
            self.status.showMessage(f"Word wrap {'on' if on else 'off'}", 1500)

    def _zoom_in(self) -> None:
        e = self.active_editor()
        if e:
            e.zoom_in()

    def _zoom_out(self) -> None:
        e = self.active_editor()
        if e:
            e.zoom_out()

    def _zoom_reset(self) -> None:
        e = self.active_editor()
        if e:
            e.zoom_reset()

    def _duplicate_line(self) -> None:
        e = self.active_editor()
        if e:
            e.duplicate_line()

    def _move_line_up(self) -> None:
        e = self.active_editor()
        if e:
            e.move_line_up()

    def _move_line_down(self) -> None:
        e = self.active_editor()
        if e:
            e.move_line_down()

    def _add_cursor(self) -> None:
        e = self.active_editor()
        if e:
            e.select_next_occurrence()

    def insert_snippet(self) -> None:
        from core import snippets
        editor = self.active_editor()
        if editor is None:
            return
        snips = snippets.for_language(editor.language)
        if not snips:
            self.status.showMessage(f"No snippets for {editor.language}", 2500)
            return
        prefixes = sorted(snips)
        choice, ok = QInputDialog.getItem(
            self, "Insert Snippet", f"{editor.language} snippet:", prefixes, 0, False)
        if not ok or not choice:
            return
        text, caret = snippets.expand(snips[choice])
        line, col = editor.getCursorPosition()
        editor.insertAt(text, line, col)
        before = text[:caret]
        if "\n" in before:
            tgt_line = line + before.count("\n")
            tgt_col = len(before.rsplit("\n", 1)[1])
        else:
            tgt_line, tgt_col = line, col + len(before)
        editor.setCursorPosition(tgt_line, tgt_col)
        editor.setFocus()

    # ------------------------------------------------------------ views
    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def toggle_zen(self) -> None:
        self._zen = not self._zen
        if self._zen:
            self._zen_state = (
                self.side_tabs.isVisible(),
                self.terminal_splitter.sizes(),
            )
            self.side_tabs.hide()
            sizes = self.terminal_splitter.sizes()
            self.terminal_splitter.setSizes([sum(sizes), 0])
            self.status.showMessage("Zen mode — Ctrl+K Z to exit", 2500)
        else:
            if self._zen_state:
                side_visible, term_sizes = self._zen_state
                self.side_tabs.setVisible(side_visible)
                self.terminal_splitter.setSizes(term_sizes)

    def open_recent_folder(self) -> None:
        recent = [f for f in self.settings.recent_folders if Path(f).is_dir()]
        if not recent:
            self.status.showMessage("No recent folders", 2000)
            return
        folder, ok = QInputDialog.getItem(
            self, "Open Recent Folder", "Folder:", recent, 0, False
        )
        if ok and folder:
            self.open_folder(folder)

    def open_recent_file(self) -> None:
        recent = [f for f in self.settings.recent_files if Path(f).is_file()]
        if not recent:
            self.status.showMessage("No recent files", 2000)
            return
        path, ok = QInputDialog.getItem(
            self, "Open Recent File", "File:", recent, 0, False
        )
        if ok and path:
            self.tabs.open_file(path)

    def show_welcome(self) -> None:
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), Welcome):
                self.tabs.setCurrentIndex(i)
                return
        page = Welcome(self.settings)
        page.open_folder_requested.connect(self.open_folder_dialog)
        page.new_file_requested.connect(self.tabs.new_file)
        page.customize_requested.connect(self.open_theme_editor)
        page.path_chosen.connect(self.open_folder)
        page.file_chosen.connect(self.tabs.open_file)
        idx = self.tabs.addTab(page, "✦ Welcome")
        self.tabs.setCurrentIndex(idx)

    def goto_definition(self) -> None:
        editor = self.active_editor()
        if editor is None or self.lsp is None:
            return
        path = editor.property("path")
        if not path:
            return
        client = self.lsp.client_for(path)
        if client is None:
            self.status.showMessage("No language server for this file", 3000)
            return
        line, col = editor.getCursorPosition()
        client.request_definition(path, line, col)

    def request_completion(self) -> None:
        editor = self.active_editor()
        if editor is None or self.lsp is None:
            return
        path = editor.property("path")
        if not path:
            return
        client = self.lsp.client_for(path)
        if client is None:
            return
        # keep the server's buffer in sync before asking for completions
        version = self._doc_versions.get(path, 1) + 1
        self._doc_versions[path] = version
        client.did_change(path, editor.text(), version)
        line, col = editor.getCursorPosition()
        client.request_completion(path, line, col)

    def _on_completions(self, items: list) -> None:
        editor = self.active_editor()
        if editor is not None and items:
            editor.show_completions(items)

    def reload_plugins(self) -> None:
        self.plugins.discover()
        if self._plugin_manager_page is not None:
            self._plugin_manager_page.refresh()
        self.status.showMessage("Plugins reloaded", 2000)

    def open_plugin_manager(self) -> None:
        from ui.plugin_manager import PluginManager
        if self._plugin_manager_page is not None:
            idx = self.tabs.indexOf(self._plugin_manager_page)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)
                self._plugin_manager_page.refresh()
                return
        page = PluginManager(self.plugins, self)
        self._plugin_manager_page = page
        idx = self.tabs.addTab(page, "🧩 Plugins")
        self.tabs.setCurrentIndex(idx)

    # ------------------------------------------------------------ autosave
    def _apply_autosave_setting(self) -> None:
        if self.settings.autosave:
            self.autosave_timer.start(2000)
        else:
            self.autosave_timer.stop()

    def _autosave_tick(self) -> None:
        editor = self.active_editor()
        if editor and editor.isModified() and editor.property("path"):
            self.act_save()

    # ------------------------------------------------------------ symbols
    def _refresh_symbols(self) -> None:
        editor = self.active_editor()
        if editor is None:
            self.symbols.clear()
            return
        self.symbols.update_for(editor.text(), editor.language)
        editor.colorize_brackets()
        if self._sticky is not None:
            self._sticky.attach(editor)
        self.minimap.attach(editor)
        self._update_breadcrumbs(editor)

    def _update_breadcrumbs(self, editor=None) -> None:
        editor = editor or self.active_editor()
        if editor is None:
            self.breadcrumbs.hide()
            return
        if not self.settings.breadcrumbs:
            self.breadcrumbs.hide()
            return
        line = editor.getCursorPosition()[0]
        self.breadcrumbs.update_for(
            editor.property("path"), editor.text(), editor.language, line)

    def _goto_symbol_line(self, line: int) -> None:
        editor = self.active_editor()
        if editor:
            editor.goto_line(line, 0)

    # ------------------------------------------------------------ git signals
    def _refresh_git_signals(self) -> None:
        editor = self.active_editor()
        if editor is None:
            self._blame_map = {}
            self.status.set_blame("")
            return
        path = editor.property("path")
        repo = getattr(self.file_tree.git, "repo", None)
        if not path or repo is None:
            editor.clear_git_markers()
            self._blame_map = {}
            self.status.set_blame("")
            return
        if self.settings.git_gutter:
            try:
                status = git_diff.line_status(repo, path, editor.text())
                editor.set_git_markers(status)
            except Exception:
                editor.clear_git_markers()
        if self.settings.git_blame and not editor.isModified():
            try:
                self._blame_map = git_diff.blame_lines(repo, path)
            except Exception:
                self._blame_map = {}
        self._update_blame_label(editor.getCursorPosition()[0])

    def _update_blame_label(self, line: int) -> None:
        if not self.settings.git_blame:
            self.status.set_blame("")
            return
        info = self._blame_map.get(line)
        if info:
            author, when, summary = info
            text = f"   {author}, {when}"
            if summary:
                text += f" · {summary[:60]}"
            self.status.set_blame(text)
        else:
            self.status.set_blame("")

    # ------------------------------------------------------------ slots
    def _on_cursor(self, line: int, col: int, language: str) -> None:
        self.status.set_position(line, col)
        self.status.set_language(language)
        self._update_blame_label(line)
        self._update_breadcrumbs()

    def _on_file_opened(self, path: str) -> None:
        self.settings.remember_file(path)
        if self.lsp is None:
            self.lsp = LspManager(str(self.root), self.settings)
        editor = self.active_editor()
        if editor is not None:
            # debounced symbol + git refresh as the user types
            editor.textChanged.connect(self._symbol_timer.start)
            editor.textChanged.connect(self._git_timer.start)
        client = self.lsp.client_for(path)
        if client and editor is not None:
            if client not in self._connected_clients:
                client.diagnostics.connect(self._on_diagnostics)
                client.completions.connect(self._on_completions)
                client.definition_found.connect(self._jump_to_error)
                self._connected_clients.add(client)
            self._doc_versions[path] = 1
            client.did_open(path, editor.text(), editor.language)
        self._refresh_symbols()
        self._refresh_git_signals()
        self.api.events.emit("file_opened", path)

    def _on_file_saved(self, path: str) -> None:
        self.file_tree.refresh_git()
        self.status.set_branch(self.file_tree.git.branch)
        self._refresh_symbols()
        self._refresh_git_signals()
        self.api.events.emit("file_saved", path)

    def _on_diagnostics(self, path: str, diagnostics: list) -> None:
        editor = self.active_editor()
        if editor is None or editor.property("path") != path:
            return
        editor.clear_diagnostics()
        lens_items = []
        for d in diagnostics:
            rng = d.get("range", {})
            start = rng.get("start", {})
            end = rng.get("end", {})
            line = start.get("line", 0)
            col = start.get("character", 0)
            length = max(end.get("character", col + 1) - col, 1)
            severity = d.get("severity", 1)
            editor.add_diagnostic(line, col, length, severity)
            message = d.get("message", "")
            if message:
                lens_items.append((line, severity, message))
        editor.set_error_lens(lens_items)

    def _on_run_state(self, running: bool) -> None:
        if running:
            # a fresh run supersedes previously parsed compiler diagnostics
            self._run_diags = {}
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if hasattr(w, "clearAnnotations"):
                    w.clearAnnotations()

    def _on_compiler_diagnostic(self, path: str, line: int, col: int,
                                severity: int, message: str) -> None:
        key = str(Path(path).resolve())
        self._run_diags.setdefault(key, []).append((line, severity, message))
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            ep = editor.property("path") if hasattr(editor, "property") else None
            if ep and str(Path(ep).resolve()) == key and hasattr(editor, "set_error_lens"):
                editor.set_error_lens(self._run_diags[key])
                editor.add_diagnostic(line, col, 1, severity)

    def _jump_to_error(self, file_path: str, line: int, col: int) -> None:
        self.active_tabs().open_file(file_path)
        editor = self.active_editor()
        if editor:
            editor.goto_line(line, col)

    def _on_theme_changed(self, theme) -> None:
        self.tabs.apply_theme(theme)
        self.titlebar.set_title(self.titlebar.title.text())
        self.backdrop.set_base_color(theme.ui.get("background", "#1e1e2e"))
        if hasattr(self, "api"):
            self.api.events.emit("theme_changed", theme)

    # ------------------------------------------------------------ teardown
    def closeEvent(self, event):  # noqa: N802
        if self.lsp:
            self.lsp.shutdown()
        self.settings.save()
        super().closeEvent(event)
