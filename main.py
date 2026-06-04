"""NeoIDE — entry point.

Creates the QApplication, loads bundled fonts, applies the saved theme and
shows the main window. Run with:  python main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase

from core.theme import ThemeManager
from core.settings import Settings
from ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parent
FONTS_DIR = ROOT / "assets" / "fonts"


def load_fonts() -> None:
    """Register any .ttf bundled under assets/fonts/ with Qt."""
    if not FONTS_DIR.exists():
        return
    for ttf in FONTS_DIR.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(ttf))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NeoIDE")
    app.setOrganizationName("NeoIDE")

    load_fonts()

    settings = Settings.load(ROOT)
    themes = ThemeManager(ROOT / "themes")
    themes.load_all()

    window = MainWindow(app=app, settings=settings, themes=themes, root=ROOT)
    themes.apply(settings.theme, app, window)
    window.show()

    # Open a folder passed on the command line, e.g. `python main.py ~/project`
    opened = False
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        if candidate.is_dir():
            window.open_folder(str(candidate))
            opened = True
    if not opened:
        # fall back to the most recently used folder so the tree isn't empty
        window.open_initial_folder()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
