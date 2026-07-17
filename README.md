<div align="center">

# NeoIDE

**A modern, hackable code editor built with Python & Qt6**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-41CD52?style=flat-square&logo=qt&logoColor=white)](https://pypi.org/project/PyQt6/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square)](https://github.com/090TYPE/neode)
[![CI](https://github.com/090TYPE/neode/actions/workflows/ci.yml/badge.svg)](https://github.com/090TYPE/neode/actions/workflows/ci.yml)

*LSP-powered autocomplete · Live themes · Full plugin system · Integrated terminal*

</div>

---

## Overview

NeoIDE is a from-scratch code editor focused on **C++ and C#** development, with support for a wide range of languages. It combines the essentials you'd expect from a modern editor — real language-server integration, a rich visual system, and a flexible plugin architecture — in a lightweight Python package.

```
python main.py path/to/your/project
```

---

## Features

### Editor
| | Feature |
|---|---|
| **Syntax** | C++, C#, Python, JSON, JS, and more via QScintilla lexers |
| **Error Lens** | Inline diagnostics from LSP + compiler output (g++, clang, MSVC) |
| **Sticky Scroll** | Enclosing function/class pinned at the top while you scroll |
| **Minimap** | Code overview on the right — click or drag to navigate |
| **Breadcrumbs** | File path + current symbol above the editor |
| **Rainbow Brackets** | Color-matched pairs with active-pair highlight |
| **Git Gutter** | Added / modified / deleted line markers vs HEAD |
| **Inline Git Blame** | Author · time · summary for the caret line |
| **Multi-cursor** | Add next occurrence with `Ctrl+D` |
| **Power Editing** | Duplicate line, move line, auto-close brackets/quotes |

### Workspace
| | Feature |
|---|---|
| **Split Editor** | Side-by-side panes with `Ctrl+\` |
| **File Tree** | Git-colored entries, file-type icons, context menu |
| **Tabbed Editor** | Dirty markers, pinned tabs, reopen closed tab (`Ctrl+Shift+T`) |
| **Find in Files** | Project-wide search with grouped results (`Ctrl+Shift+F`) |
| **Symbols Outline** | Class/function tree (`Ctrl+Shift+O`), click to jump |
| **Quick Open** | Fuzzy file finder (`Ctrl+P`) |
| **Command Palette** | Fuzzy-search all commands (`Ctrl+Shift+P`) |
| **Markdown Preview** | Live rendered preview (`Ctrl+Shift+V`) |
| **Welcome Tab** | Recent folders & files on startup |

### Terminal & Run
| | Feature |
|---|---|
| **Integrated Terminal** | Multiple tabs, Stop/Clear, run timing |
| **Run Any File** | C/C++, C#, Python, JS/TS, Go, Rust, Java, Ruby, PHP, Bash, Lua… |
| **Error Parsing** | Double-click a compiler error to jump to the line |
| **Package Manager** | pip / npm / yarn / cargo / go / gem / composer / .NET / Gradle |

### Themes & Appearance
| | Feature |
|---|---|
| **7 Bundled Themes** | Catppuccin Mocha, Nord, One Dark, Tokyo Night, Solarized Dark, Light Clean, Synthwave |
| **Live Switching** | Theme changes apply instantly — no restart |
| **Visual Theme Editor** | Color pickers for every UI & syntax token (`Ctrl+K Ctrl+T`) |
| **Background Image** | Wallpaper behind the UI *and* behind the code, with fit mode & opacity |
| **Custom Themes** | Save As writes your design to `themes/your_name.json` |

### LSP & Intelligence
| | Feature |
|---|---|
| **Autocomplete** | LSP completions (`Ctrl+Space`) |
| **Diagnostics** | Real-time error/warning squiggles |
| **Go to Definition** | `F12` |
| **clangd** | C++ — install via LLVM |
| **OmniSharp** | C# — drop in any OmniSharp-roslyn build |

### Plugin System
| | Feature |
|---|---|
| **Hot Reload** | Enable/disable plugins without restarting |
| **User Folder** | Drop `~/.neode/plugins/my_plugin.py` — no repo changes needed |
| **Bundled Plugins** | TODO Tree, Formatter, Git Panel (commit), Word Count, Clock |
| **Rich API** | Editor, terminal, UI panels, status bar, events, storage, runners |

---

## Install

```bash
git clone https://github.com/090TYPE/neode.git
cd neode

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Language Servers (optional but recommended)

```bash
# C++ — clangd
winget install LLVM.LLVM          # Windows
sudo apt install clangd            # Ubuntu/Debian
brew install llvm                  # macOS

# C# — OmniSharp
# Download a build from https://github.com/OmniSharp/omnisharp-roslyn/releases
# Then set the path in Settings → LSP
```

### Fonts (optional)

Drop `JetBrainsMono-*.ttf` files into `assets/fonts/` for the intended look. The editor falls back to your system monospace font if absent.

---

## Run

```bash
python main.py                      # empty workspace
python main.py path/to/project      # open a folder immediately
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+P` | Command Palette |
| `Ctrl+P` | Quick Open |
| `Ctrl+N` / `Ctrl+O` | New / Open file |
| `Ctrl+S` / `Ctrl+Shift+S` | Save / Save As |
| `Ctrl+W` | Close tab |
| `Ctrl+Shift+T` | Reopen closed tab |
| `Ctrl+\` | Split editor |
| `Ctrl+F` / `Ctrl+H` | Find / Replace |
| `F3` / `Shift+F3` | Find next / previous |
| `Ctrl+G` | Go to line |
| `Ctrl+/` | Toggle line comment |
| `Ctrl+Space` | Trigger LSP autocomplete |
| `F12` | Go to definition |
| `F5` / `Shift+F5` | Run file / Stop |
| `Ctrl+Shift+F` | Find in Files |
| `Ctrl+Shift+V` | Markdown preview |
| `Ctrl+Shift+O` | Symbols outline |
| `` Ctrl+` `` | Toggle terminal |
| `Ctrl+,` | Settings tab |
| `Ctrl+D` | Add next occurrence (multi-cursor) |
| `Ctrl+Shift+D` | Duplicate line |
| `Alt+↑` / `Alt+↓` | Move line up / down |
| `Ctrl+K Z` | Zen mode |
| `F11` | Fullscreen |
| `Ctrl+K Ctrl+T` | Visual theme editor |
| `Shift+Alt+F` | Format document |
| `Alt+Z` | Toggle word wrap |
| `Ctrl+=` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset |

---

## Architecture

```
neode/
├── main.py                   Entry point — QApplication, fonts, theme
├── core/
│   ├── settings.py           JSON-persisted user settings
│   ├── theme.py              JSON theme → QSS + lexer colour mapping
│   ├── editor.py             QScintilla editor + all decorations
│   ├── editor_tabs.py        Tab container — open / save / dirty tracking
│   ├── file_tree.py          File tree with Git colours & context menu
│   ├── git_integration.py    pygit2 wrapper (blame, status, commit)
│   ├── terminal.py           QProcess terminal + runner + error parser
│   └── lsp_client.py         JSON-RPC LSP client + per-language manager
├── ui/
│   ├── main_window.py        Frameless shell wiring everything together
│   ├── titlebar.py           Custom drag/resize titlebar
│   ├── statusbar.py          Branch · language · Ln/Col · encoding
│   ├── command_palette.py    Ctrl+Shift+P fuzzy palette
│   ├── quick_open.py         Ctrl+P fuzzy file finder
│   ├── find_bar.py           Find & Replace with regex / case / whole-word
│   ├── symbols_panel.py      Class/function outline
│   ├── settings_dialog.py    Settings tab (appearance, editor, LSP)
│   └── theme_editor.py       Visual colour/font theme editor
├── plugins/
│   ├── base.py               BasePlugin class
│   ├── loader.py             Plugin discovery, lifecycle, hot-reload
│   ├── api.py                Plugin API facades
│   ├── todo_tree.py          Bundled — TODO/FIXME tree
│   ├── formatter.py          Bundled — document formatter
│   └── git_panel.py          Bundled — Git commit panel
└── themes/
    ├── catppuccin_mocha.json
    ├── nord.json
    ├── one_dark.json
    ├── tokyo_night.json
    ├── solarized_dark.json
    └── light_clean.json
```

The theme pipeline is the design centrepiece: **JSON → `ThemeManager` → QSS for the app + style mapping for each QScintilla lexer**, applied live to every open editor with no restart.

---

## Writing a Plugin

Drop a file into `~/.neode/plugins/my_plugin.py` — no repo changes needed:

```python
from plugins.base import BasePlugin

class Plugin(BasePlugin):
    name        = "My Plugin"
    version     = "1.0.0"
    author      = "you"
    description = "What it does."

    def activate(self):
        self.api.ui.register_command("Say Hi", self.hi)
        self.badge = self.api.statusbar.add_text("hi 👋")
        self.api.events.on("file_saved", lambda path: print("saved", path))

    def hi(self):
        self.api.ui.show_notification("Hello from a plugin!")
        self.storage.set("greeted", True)   # persisted across restarts
```

### Plugin API

| Facade | What you can do |
|---|---|
| `api.editor` | get/set text, selection, cursor, current path & language, insert |
| `api.terminal` | `run(cmd)`, `run_file(path)` |
| `api.ui` | `register_command`, `show_notification`, `add_panel`, `add_tab`, `open_file` |
| `api.statusbar` | `add_text`, `add_widget`, `remove` |
| `api.git` | repo status + commit |
| `api.lang` | `register_runner(ext, template)`, `register_theme(dict)` |
| `api.storage` | `self.storage.get/set` — per-plugin JSON store |
| `api.events` | `on(event, cb)` — `app_ready`, `folder_opened`, `file_opened`, `before_save`, `file_saved`, `file_closed`, `theme_changed` |

---

## Build a Binary

```bash
pyinstaller build.spec
# Output: dist/NeoIDE(.exe)
```

---

## Themes

Edit any file in `themes/` or use the **Visual Theme Editor** (`Ctrl+K Ctrl+T`) to customize colors, font, and corner radius live. The schema:

```json
{
  "name": "My Theme",
  "author": "you",
  "ui": {
    "background":   "#1e1e2e",
    "foreground":   "#cdd6f4",
    "accent":       "#89b4fa",
    "panel":        "#181825",
    "border":       "#313244",
    "selection":    "#45475a",
    "hover":        "#313244",
    "radius":       "6px"
  },
  "syntax": {
    "keyword":      "#cba6f7",
    "string":       "#a6e3a1",
    "comment":      "#6c7086",
    "number":       "#fab387",
    "function":     "#89b4fa",
    "class":        "#f9e2af",
    "operator":     "#89dceb",
    "variable":     "#cdd6f4"
  },
  "font": {
    "family": "JetBrains Mono",
    "size": 13
  }
}
```

---

## License

MIT — see [LICENSE](LICENSE).


---

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

1. Fork the repo
2. Create your feature branch: `git checkout -b feat/your-feature`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push and open a PR

---

## License

MIT © [090TYPE](https://github.com/090TYPE)
