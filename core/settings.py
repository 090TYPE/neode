"""Persistent IDE settings stored as JSON next to the application."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class Settings:
    theme: str = "dark_synthwave"
    font_family: str = "JetBrains Mono"
    font_size: int = 13
    autosave: bool = False
    recent_folders: list[str] = field(default_factory=list)
    recent_files: list[str] = field(default_factory=list)
    disabled_plugins: list[str] = field(default_factory=list)
    clangd_path: str = "clangd"
    omnisharp_path: str = "omnisharp"
    python_path: str = ""

    # editor preferences
    tab_width: int = 4
    show_line_numbers: bool = True
    highlight_current_line: bool = True
    word_wrap: bool = False
    show_whitespace: bool = False
    indent_guides: bool = True
    show_folding: bool = True
    auto_pair: bool = True
    error_lens: bool = True
    git_gutter: bool = True
    git_blame: bool = True
    rainbow_brackets: bool = True
    sticky_scroll: bool = True
    file_icons: bool = True
    minimap: bool = True
    breadcrumbs: bool = True
    anthropic_api_key: str = ""

    # background image / appearance
    bg_image: str = ""
    bg_mode: str = "cover"          # cover | contain | stretch | center | tile
    bg_opacity: int = 70            # 0 = image hidden, 100 = fully visible
    panel_opacity: int = 76         # chrome surface opacity over wallpaper
    editor_translucent: bool = True  # let the image show behind code too

    # populated at load time, not serialized
    _path: Path | None = field(default=None, repr=False, compare=False)

    @classmethod
    def load(cls, root: Path) -> "Settings":
        path = root / "settings.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data.pop("_path", None)
                obj = cls(**data)
            except (json.JSONDecodeError, TypeError):
                obj = cls()
        else:
            obj = cls()
        obj._path = path
        return obj

    def save(self) -> None:
        if self._path is None:
            return
        data = asdict(self)
        data.pop("_path", None)
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def remember_folder(self, folder: str) -> None:
        if folder in self.recent_folders:
            self.recent_folders.remove(folder)
        self.recent_folders.insert(0, folder)
        self.recent_folders = self.recent_folders[:10]
        self.save()

    def remember_file(self, file: str) -> None:
        if file in self.recent_files:
            self.recent_files.remove(file)
        self.recent_files.insert(0, file)
        self.recent_files = self.recent_files[:15]
        self.save()
