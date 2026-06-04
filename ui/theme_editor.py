"""Visual Theme Editor — tweak every UI/syntax colour and the font live, then
save the result as your own JSON theme.

Every change is applied to the whole app instantly (live preview). "Save As…"
writes a new file to themes/ so it survives restarts and shows up in the theme
picker. Closing without saving reverts to the theme you started from.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFontComboBox, QSpinBox, QInputDialog, QColorDialog,
    QFrame, QLineEdit
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal

from core.theme import Theme, UI_KEYS, SYNTAX_KEYS


def parse_color(value: str) -> QColor:
    s = (value or "").lstrip("#")
    if len(s) == 8:  # RRGGBBAA
        try:
            r, g, b, a = (int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
            return QColor(r, g, b, a)
        except ValueError:
            return QColor("#000000")
    c = QColor("#" + s) if s else QColor("#000000")
    return c if c.isValid() else QColor("#000000")


def format_color(c: QColor) -> str:
    if c.alpha() == 255:
        return c.name()  # #rrggbb
    return "#{:02x}{:02x}{:02x}{:02x}".format(
        c.red(), c.green(), c.blue(), c.alpha()
    )


class ColorButton(QPushButton):
    """A swatch button that opens a colour picker and shows the hex value."""
    changed = pyqtSignal(str)

    def __init__(self, value: str, allow_alpha: bool = False):
        super().__init__()
        self._allow_alpha = allow_alpha
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_value(value)
        self.clicked.connect(self._pick)

    def set_value(self, value: str) -> None:
        self._value = value
        c = parse_color(value)
        # readable text colour on top of the swatch
        text = "#000000" if c.lightnessF() > 0.55 else "#ffffff"
        self.setText(value)
        self.setStyleSheet(
            f"QPushButton {{ background-color: {value}; color: {text};"
            f" border: 1px solid rgba(127,127,127,0.5); border-radius: 6px;"
            f" padding: 4px 8px; text-align: left; }}"
        )

    def value(self) -> str:
        return self._value

    def _pick(self) -> None:
        opts = QColorDialog.ColorDialogOption.ShowAlphaChannel if self._allow_alpha \
            else QColorDialog.ColorDialogOption(0)
        c = QColorDialog.getColor(
            parse_color(self._value), self, "Pick colour", opts
        )
        if c.isValid():
            v = format_color(c)
            self.set_value(v)
            self.changed.emit(v)


class ThemeEditor(QDialog):
    def __init__(self, themes, settings, app, root_window, parent=None):
        super().__init__(parent)
        self.themes = themes
        self.settings = settings
        self.app = app
        self.root_window = root_window

        base = themes.current or Theme.from_dict({})
        self._original = base.copy()
        self._working = base.copy()

        self.setWindowTitle("Theme Editor")
        self.resize(560, 640)

        root = QVBoxLayout(self)

        # name row
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit(self._working.name)
        self.name_edit.textChanged.connect(self._on_name)
        name_row.addWidget(self.name_edit, 1)
        root.addLayout(name_row)

        # scrollable colour sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(14)

        body_layout.addWidget(self._section_label("Interface colours"))
        body_layout.addLayout(self._color_grid(
            UI_KEYS, self._working.ui, alpha_keys={"selection", "line_highlight"}
        ))

        body_layout.addWidget(self._section_label("Syntax colours"))
        body_layout.addLayout(self._color_grid(SYNTAX_KEYS, self._working.syntax))

        body_layout.addWidget(self._section_label("Font"))
        body_layout.addLayout(self._font_row())

        body_layout.addWidget(self._section_label("Corner radius"))
        body_layout.addLayout(self._radius_row())

        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # action buttons
        actions = QHBoxLayout()
        revert = QPushButton("Revert")
        revert.clicked.connect(self._revert)
        save = QPushButton("Save As…")
        save.setDefault(True)
        save.clicked.connect(self._save_as)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        actions.addWidget(revert)
        actions.addStretch(1)
        actions.addWidget(close)
        actions.addWidget(save)
        root.addLayout(actions)

        self._apply_live()

    # ------------------------------------------------------------ builders
    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        return lbl

    def _color_grid(self, keys, target: dict, alpha_keys=frozenset()) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        for i, (key, label, default) in enumerate(keys):
            row, col = divmod(i, 2)
            value = target.get(key, default)
            target.setdefault(key, value)
            cell = QVBoxLayout()
            cell.setSpacing(2)
            cell.addWidget(QLabel(label))
            btn = ColorButton(value, allow_alpha=key in alpha_keys)
            btn.changed.connect(lambda v, k=key, t=target: self._set(t, k, v))
            cell.addWidget(btn)
            holder = QWidget()
            holder.setLayout(cell)
            grid.addWidget(holder, row, col)
        return grid

    def _font_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.font_combo = QFontComboBox()
        fam = self._working.font.get("family", "JetBrains Mono")
        self.font_combo.setCurrentFont(QFont(fam))
        self.font_combo.currentFontChanged.connect(
            lambda f: self._set_font("family", f.family())
        )
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 32)
        self.size_spin.setValue(int(self._working.font.get("size", 13)))
        self.size_spin.valueChanged.connect(lambda v: self._set_font("size", v))
        row.addWidget(QLabel("Family"))
        row.addWidget(self.font_combo, 1)
        row.addWidget(QLabel("Size"))
        row.addWidget(self.size_spin)
        return row

    def _radius_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(0, 16)
        self.radius_spin.setValue(int(self._working.ui.get("radius", 6)))
        self.radius_spin.valueChanged.connect(self._set_radius)
        row.addWidget(QLabel("Rounded corners (px)"))
        row.addWidget(self.radius_spin)
        row.addStretch(1)
        return row

    # ------------------------------------------------------------ mutation
    def _set(self, target: dict, key: str, value: str) -> None:
        target[key] = value
        self._apply_live()

    def _set_font(self, key: str, value) -> None:
        self._working.font[key] = value
        self._apply_live()

    def _set_radius(self, value: int) -> None:
        self._working.ui["radius"] = value
        self._apply_live()

    def _on_name(self, text: str) -> None:
        self._working.name = text or "Custom Theme"

    def _apply_live(self) -> None:
        self.themes.apply_object(self._working, self.app, self.root_window)

    def _revert(self) -> None:
        self._working = self._original.copy()
        self.themes.apply_object(self._original, self.app, self.root_window)
        self.name_edit.setText(self._working.name)
        # rebuild would be heavy; closing & reopening reflects swatches.
        self.themes.apply_object(self._working, self.app, self.root_window)

    # ------------------------------------------------------------ save / close
    def _save_as(self) -> None:
        default = self._working.name if self._working.name not in ("", "Unnamed") \
            else "My Theme"
        name, ok = QInputDialog.getText(self, "Save Theme", "Theme name:", text=default)
        if not ok or not name.strip():
            return
        self._working.name = name.strip()
        self._working.author = self._working.author or "You"
        theme_id = self.themes.save_theme(self._working.copy())
        self.settings.theme = theme_id
        self.settings.save()
        self.themes.apply(theme_id, self.app, self.root_window)
        self.accept()

    def reject(self) -> None:
        # revert live preview to where we started
        self.themes.apply_object(self._original, self.app, self.root_window)
        super().reject()
