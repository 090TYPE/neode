"""Theme system: JSON themes -> QSS + QScintilla lexer colours.

A theme is a JSON file (see themes/*.json) with sections ``ui``, ``syntax`` and
``font``. ThemeManager loads them all, generates a polished QSS string for the
whole application and exposes the raw colour maps so editors can recolour their
lexers when the theme changes. Themes can be edited live and saved back to disk
from the in-app Theme Editor.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget

# canonical keys the Theme Editor exposes, with human labels and defaults
UI_KEYS = [
    ("background",     "Background",        "#1e1e2e"),
    ("surface",        "Surface / panels",  "#181825"),
    ("accent",         "Accent",            "#89b4fa"),
    ("text_primary",   "Text",              "#cdd6f4"),
    ("text_secondary", "Text (muted)",      "#a6adc8"),
    ("border",         "Borders",           "#313244"),
    ("selection",      "Selection",         "#45475a"),
    ("line_highlight", "Current line",      "#ffffff10"),
]
SYNTAX_KEYS = [
    ("keyword",      "Keyword",       "#cba6f7"),
    ("string",       "String",        "#a6e3a1"),
    ("comment",      "Comment",       "#6c7086"),
    ("number",       "Number",        "#fab387"),
    ("type",         "Type / class",  "#f9e2af"),
    ("function",     "Function",      "#89b4fa"),
    ("preprocessor", "Preprocessor",  "#f38ba8"),
    ("operator",     "Operator",      "#89dceb"),
]


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB[AA] into a CSS rgba() string at the given 0..1 alpha."""
    h = hex_color.lstrip("#")
    if len(h) < 6:
        h = (h + "000000")[:6]
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {max(0.0, min(1.0, alpha)):.3f})"


def _mix(hex_a: str, hex_b: str, t: float) -> str:
    """Linearly blend two #RRGGBB colours (ignores alpha)."""
    def parse(h):
        h = h.lstrip("#")[:6].ljust(6, "0")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    ar, ag, ab = parse(hex_a)
    br, bg, bb = parse(hex_b)
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    b = round(ab + (bb - ab) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class Theme:
    name: str
    author: str
    ui: dict
    syntax: dict
    font: dict

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        return cls(
            name=data.get("name", "Unnamed"),
            author=data.get("author", ""),
            ui=dict(data.get("ui", {})),
            syntax=dict(data.get("syntax", {})),
            font=dict(data.get("font", {})),
        )

    def copy(self) -> "Theme":
        return Theme(self.name, self.author, dict(self.ui), dict(self.syntax),
                     dict(self.font))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "author": self.author,
            "ui": self.ui,
            "syntax": self.syntax,
            "font": self.font,
        }

    def color(self, key: str, fallback: str = "#000000") -> str:
        return self.ui.get(key, fallback)


class ThemeManager:
    def __init__(self, themes_dir: Path):
        self.themes_dir = themes_dir
        self.themes: dict[str, Theme] = {}
        self.current: Theme | None = None
        self._app: QApplication | None = None
        self._root: QWidget | None = None
        # when a wallpaper is active the chrome is rendered translucent
        self.backdrop_active = False
        self.panel_alpha = 1.0
        # subscribers notified when a new theme is applied (e.g. editors)
        self._listeners: list = []

    def load_all(self) -> None:
        self.themes.clear()
        if not self.themes_dir.exists():
            return
        for path in sorted(self.themes_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.themes[path.stem] = Theme.from_dict(data)
            except (json.JSONDecodeError, OSError):
                continue

    def names(self) -> list[str]:
        return list(self.themes.keys())

    def on_change(self, callback) -> None:
        self._listeners.append(callback)

    # ------------------------------------------------------------ applying
    def apply(self, theme_id: str, app: QApplication, root: QWidget) -> None:
        theme = self.themes.get(theme_id)
        if theme is None and self.themes:
            theme = next(iter(self.themes.values()))
        if theme is None:
            return
        self.apply_object(theme, app, root)

    def apply_object(self, theme: Theme, app: QApplication | None = None,
                     root: QWidget | None = None) -> None:
        """Apply a Theme instance directly (used for live preview/editing)."""
        app = app or self._app
        root = root or self._root
        if app is None:
            return
        self._app, self._root = app, root
        self.current = theme
        app.setStyleSheet(self.build_qss(theme))
        for cb in self._listeners:
            try:
                cb(theme)
            except Exception:  # a listener must never break theme switching
                pass

    def reapply(self) -> None:
        if self.current is not None:
            self.apply_object(self.current)

    # ------------------------------------------------------------ persistence
    def slugify(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        return slug or "custom_theme"

    def save_theme(self, theme: Theme) -> str:
        """Write a theme to themes/<slug>.json and register it. Returns its id."""
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        theme_id = self.slugify(theme.name)
        path = self.themes_dir / f"{theme_id}.json"
        path.write_text(
            json.dumps(theme.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.themes[theme_id] = theme
        return theme_id

    # ------------------------------------------------------------ stylesheet
    def build_qss(self, theme: Theme) -> str:
        ui = theme.ui
        font = theme.font
        bg = ui.get("background", "#1e1e2e")
        surface = ui.get("surface", "#181825")
        accent = ui.get("accent", "#89b4fa")
        text = ui.get("text_primary", "#cdd6f4")
        text2 = ui.get("text_secondary", "#a6adc8")
        border = ui.get("border", "#313244")
        selection = ui.get("selection", "#45475a")
        family = font.get("family", "JetBrains Mono")
        size = int(font.get("size", 13))
        radius = int(ui.get("radius", 6))

        # derived shades for a layered, modern look
        elevated = _mix(surface, text, 0.05)      # slightly lighter than surface
        hover = _mix(surface, text, 0.12)
        accent_soft = _mix(bg, accent, 0.35)
        title_bg = _mix(bg, surface, 0.5)

        # when a wallpaper is active, render chrome translucent over the backdrop
        if self.backdrop_active:
            a = self.panel_alpha
            base_bg = "transparent"
            surface = _rgba(surface, min(a + 0.04, 1.0))
            elevated = _rgba(elevated, min(a + 0.08, 1.0))
            title_bg = _rgba(title_bg, a)
            surface_solid = _mix(bg, text, 0.05)  # for popups that need to be opaque
        else:
            base_bg = bg
            surface_solid = surface

        return f"""
        * {{
            font-family: "{family}", "Segoe UI", "Inter", sans-serif;
            font-size: {size}px;
            outline: none;
        }}
        QWidget {{ background-color: {base_bg}; color: {text}; }}
        #Backdrop {{ background: transparent; }}
        QMainWindow {{ background-color: {bg}; }}
        QDialog {{ background-color: {surface_solid}; }}
        QDialog {{ border: 1px solid {border}; }}
        QLabel {{ background: transparent; }}

        /* ---- title bar ---- */
        #TitleBar {{
            background-color: {title_bg};
            border-bottom: 1px solid {border};
        }}
        #TitleBar QLabel {{ color: {text}; }}
        #TitleBar QPushButton {{
            background: transparent; border: none; color: {text2};
            border-radius: {radius}px;
        }}
        #TitleBar QPushButton:hover {{ background-color: {hover}; color: {text}; }}
        #TitleBar QPushButton#closeButton:hover {{
            background-color: #f38ba8; color: {bg};
        }}

        /* ---- action toolbar ---- */
        #ActionToolBar {{
            background-color: {title_bg};
            border-bottom: 1px solid {border};
        }}
        #ActionToolBar QToolButton {{ padding: 4px 10px; color: {text}; }}
        #ActionToolBar QToolButton:hover {{ background-color: {hover}; }}
        #ActionToolBar QToolButton#runButton {{ color: #3fb950; font-weight: 600; }}
        #ActionToolBar QToolButton#runButton:disabled {{ color: {text2}; }}
        #ActionToolBar QFrame {{ color: {border}; }}

        /* ---- plugin cards / settings sections ---- */
        #PluginCard {{
            background-color: {surface_solid if self.backdrop_active else surface};
            border: 1px solid {border};
            border-radius: {radius}px;
        }}

        /* ---- breadcrumbs ---- */
        #Breadcrumbs {{
            background-color: {title_bg};
            border-bottom: 1px solid {border};
        }}
        #Breadcrumbs QLabel#Crumb {{ color: {text2}; padding: 0 2px; }}
        #Breadcrumbs QLabel#Crumb:hover {{ color: {accent}; }}

        /* ---- sticky scroll ---- */
        #StickyScroll {{
            background-color: {surface_solid if self.backdrop_active else surface};
            border-bottom: 1px solid {accent};
        }}
        #StickyScroll QLabel#StickyRow {{ padding: 1px 12px; color: {text2}; }}
        #StickyScroll QLabel#StickyRow:hover {{
            background-color: {hover}; color: {text};
        }}

        /* ---- splitters ---- */
        QSplitter::handle {{ background-color: {bg}; }}
        QSplitter::handle:horizontal {{ width: 2px; }}
        QSplitter::handle:vertical {{ height: 2px; }}
        QSplitter::handle:hover {{ background-color: {accent}; }}

        /* ---- lists / trees / inputs ---- */
        QTreeView, QListWidget {{
            background-color: {surface};
            border: none;
            padding: 4px;
        }}
        QPlainTextEdit, QLineEdit, QTextEdit, QSpinBox, QComboBox {{
            background-color: {elevated};
            border: 1px solid {border};
            border-radius: {radius}px;
            padding: 5px 8px;
            selection-background-color: {selection};
            selection-color: {text};
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 1px solid {accent};
        }}
        QTreeView::item, QListWidget::item {{
            padding: 3px; border-radius: {radius - 2 if radius > 2 else 0}px;
        }}
        QTreeView::item:hover, QListWidget::item:hover {{ background-color: {hover}; }}
        QTreeView::item:selected, QListWidget::item:selected {{
            background-color: {accent_soft}; color: {text};
        }}

        QComboBox::drop-down {{ border: none; width: 18px; }}
        QComboBox QAbstractItemView {{
            background-color: {surface_solid}; border: 1px solid {border};
            selection-background-color: {accent_soft};
        }}

        /* ---- tabs ---- */
        QTabWidget::pane {{ border: none; }}
        QTabBar {{ background: {base_bg}; }}
        QTabBar::tab {{
            background-color: {base_bg};
            color: {text2};
            padding: 7px 16px;
            border: none;
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:hover {{ color: {text}; }}
        QTabBar::tab:selected {{
            background-color: {surface};
            color: {text};
            border-bottom: 2px solid {accent};
        }}

        /* ---- buttons ---- */
        QPushButton {{
            background-color: {elevated};
            color: {text};
            border: 1px solid {border};
            border-radius: {radius}px;
            padding: 6px 14px;
        }}
        QPushButton:hover {{ background-color: {hover}; border-color: {accent}; }}
        QPushButton:pressed {{ background-color: {accent}; color: {bg}; }}
        QPushButton:default {{ border: 1px solid {accent}; }}

        QToolButton {{
            background: transparent; border: none; border-radius: {radius}px;
            padding: 4px 6px; color: {text2};
        }}
        QToolButton:hover {{ background-color: {hover}; color: {text}; }}
        QToolButton:checked {{ background-color: {accent_soft}; color: {text}; }}

        /* ---- checkbox / slider ---- */
        QCheckBox {{ background: transparent; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px; border-radius: 4px;
            border: 1px solid {border}; background: {elevated};
        }}
        QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
        QSlider::groove:horizontal {{
            height: 4px; background: {border}; border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {accent}; width: 14px; margin: -6px 0; border-radius: 7px;
        }}

        /* ---- menus ---- */
        QMenu {{
            background-color: {surface_solid}; border: 1px solid {border};
            border-radius: {radius}px; padding: 4px;
        }}
        QMenu::item {{ padding: 5px 22px; border-radius: {radius - 2 if radius > 2 else 0}px; }}
        QMenu::item:selected {{ background-color: {accent_soft}; color: {text}; }}

        /* ---- scrollbars ---- */
        QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
        QScrollBar::handle:vertical {{
            background: {border}; border-radius: 6px; min-height: 28px; margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {text2}; }}
        QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
        QScrollBar::handle:horizontal {{
            background: {border}; border-radius: 6px; min-width: 28px; margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {text2}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

        /* ---- status bar & tooltip ---- */
        QStatusBar {{ background-color: {title_bg}; color: {text2}; }}
        QStatusBar::item {{ border: none; }}
        QToolTip {{
            background-color: {surface}; color: {text};
            border: 1px solid {accent}; border-radius: {radius}px; padding: 4px 6px;
        }}
        """
