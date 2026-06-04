"""Settings as a full in-editor page (opened as a tab, like VS Code).

Sections: Appearance, Background image, Editor, Language servers. Saving writes
to settings.json and emits ``saved`` so the window can re-apply everything live.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QSlider,
    QSpinBox, QCheckBox, QLineEdit, QPushButton, QFontComboBox, QScrollArea,
    QFrame, QFileDialog
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer, pyqtSignal


class _Section(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("SettingsSection")
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 18)
        self.form.setSpacing(8)
        header = QLabel(title)
        f = header.font()
        f.setPointSize(f.pointSize() + 2)
        f.setBold(True)
        header.setFont(f)
        self.form.addRow(header)

    def row(self, label: str, widget) -> None:
        self.form.addRow(label, widget)


class SettingsPage(QWidget):
    saved = pyqtSignal()
    edit_theme_requested = pyqtSignal()
    background_changed = pyqtSignal()   # live preview while editing

    def __init__(self, settings, theme_names: list[str], parent=None):
        super().__init__(parent)
        self.settings = settings
        self._bg_timer = QTimer(self)
        self._bg_timer.setSingleShot(True)
        self._bg_timer.setInterval(80)
        self._bg_timer.timeout.connect(self._bg_live)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(28, 22, 28, 22)
        col.setSpacing(6)

        title = QLabel("Settings")
        tf = title.font(); tf.setPointSize(tf.pointSize() + 6); tf.setBold(True)
        title.setFont(tf)
        col.addWidget(title)
        col.addSpacing(10)

        col.addWidget(self._appearance(theme_names))
        col.addWidget(self._background())
        col.addWidget(self._editor())
        col.addWidget(self._language_servers())
        col.addStretch(1)

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # sticky save bar
        bar = QHBoxLayout()
        bar.setContentsMargins(28, 8, 28, 12)
        bar.addStretch(1)
        save = QPushButton("Save & Apply")
        save.setDefault(True)
        save.clicked.connect(self._save)
        bar.addWidget(save)
        outer.addLayout(bar)

    # ------------------------------------------------------------ sections
    def _appearance(self, theme_names) -> _Section:
        s = _Section("Appearance")
        row = QHBoxLayout()
        self.theme = QComboBox()
        self.theme.addItems(theme_names)
        if self.settings.theme in theme_names:
            self.theme.setCurrentText(self.settings.theme)
        customize = QPushButton("Customize…")
        customize.clicked.connect(self.edit_theme_requested.emit)
        row.addWidget(self.theme, 1)
        row.addWidget(customize)
        s.row("Theme", self._wrap(row))

        self.font_family = QFontComboBox()
        self.font_family.setCurrentFont(QFont(self.settings.font_family))
        s.row("Font family", self.font_family)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 32)
        self.font_size.setValue(self.settings.font_size)
        s.row("Font size", self.font_size)
        return s

    def _background(self) -> _Section:
        s = _Section("Background image")
        path_row = QHBoxLayout()
        self.bg_image = QLineEdit(self.settings.bg_image)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_image)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self.bg_image.clear())
        path_row.addWidget(self.bg_image, 1)
        path_row.addWidget(browse)
        path_row.addWidget(clear)
        s.row("Image", self._wrap(path_row))

        self.bg_mode = QComboBox()
        self.bg_mode.addItems(["cover", "contain", "stretch", "center", "tile"])
        self.bg_mode.setCurrentText(self.settings.bg_mode)
        s.row("Fit", self.bg_mode)

        self.bg_opacity = self._slider(0, 100, self.settings.bg_opacity)
        s.row("Image visibility", self.bg_opacity["w"])

        self.panel_opacity = self._slider(40, 100, self.settings.panel_opacity)
        s.row("Panel opacity", self.panel_opacity["w"])

        self.editor_translucent = QCheckBox("Show image behind code too")
        self.editor_translucent.setChecked(self.settings.editor_translucent)
        s.row("", self.editor_translucent)

        hint = QLabel("Pick an image and it appears instantly — drag the sliders "
                      "to taste. Higher visibility + lower panel opacity = bolder.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6c7086;")
        s.row("", hint)

        # live preview: any change re-applies the background immediately
        self.bg_image.textChanged.connect(self._bg_timer.start)
        self.bg_mode.currentTextChanged.connect(self._bg_timer.start)
        self.bg_opacity["slider"].valueChanged.connect(self._bg_timer.start)
        self.panel_opacity["slider"].valueChanged.connect(self._bg_timer.start)
        self.editor_translucent.toggled.connect(self._bg_timer.start)
        return s

    def _editor(self) -> _Section:
        s = _Section("Editor")
        self.tab_width = QSpinBox()
        self.tab_width.setRange(1, 8)
        self.tab_width.setValue(self.settings.tab_width)
        s.row("Tab width", self.tab_width)

        self.autosave = QCheckBox("Autosave changed files")
        self.autosave.setChecked(self.settings.autosave)
        s.row("", self.autosave)

        self.line_numbers = self._check("Line numbers", self.settings.show_line_numbers)
        s.row("", self.line_numbers)
        self.caret_line = self._check("Highlight current line", self.settings.highlight_current_line)
        s.row("", self.caret_line)
        self.wrap = self._check("Word wrap", self.settings.word_wrap)
        s.row("", self.wrap)
        self.whitespace = self._check("Show whitespace", self.settings.show_whitespace)
        s.row("", self.whitespace)
        self.guides = self._check("Indentation guides", self.settings.indent_guides)
        s.row("", self.guides)
        self.folding = self._check("Code folding", self.settings.show_folding)
        s.row("", self.folding)
        self.auto_pair = self._check("Auto-close brackets & quotes", self.settings.auto_pair)
        s.row("", self.auto_pair)
        self.error_lens = self._check("Error Lens (inline diagnostics)", self.settings.error_lens)
        s.row("", self.error_lens)
        self.git_gutter = self._check("Git change markers (gutter)", self.settings.git_gutter)
        s.row("", self.git_gutter)
        self.git_blame = self._check("Inline git blame (status bar)", self.settings.git_blame)
        s.row("", self.git_blame)
        self.rainbow = self._check("Rainbow brackets", self.settings.rainbow_brackets)
        s.row("", self.rainbow)
        self.sticky = self._check("Sticky scroll (pinned scope header)", self.settings.sticky_scroll)
        s.row("", self.sticky)
        self.file_icons = self._check("File-type icons in tree", self.settings.file_icons)
        s.row("", self.file_icons)
        self.minimap = self._check("Minimap", self.settings.minimap)
        s.row("", self.minimap)
        self.breadcrumbs = self._check("Breadcrumbs bar", self.settings.breadcrumbs)
        s.row("", self.breadcrumbs)
        return s

    def _language_servers(self) -> _Section:
        s = _Section("Tools & language servers")
        self.python_path = QLineEdit(self.settings.python_path)
        self.python_path.setPlaceholderText("auto-detect (uses project venv if present)")
        s.row("Python path", self.python_path)
        self.anthropic_api_key = QLineEdit(self.settings.anthropic_api_key)
        self.anthropic_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_api_key.setPlaceholderText("sk-ant-… (for the AI assistant)")
        s.row("Anthropic API key", self.anthropic_api_key)
        self.clangd = QLineEdit(self.settings.clangd_path)
        s.row("clangd path", self.clangd)
        self.omnisharp = QLineEdit(self.settings.omnisharp_path)
        s.row("OmniSharp path", self.omnisharp)
        return s

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    @staticmethod
    def _check(text: str, value: bool) -> QCheckBox:
        c = QCheckBox(text)
        c.setChecked(value)
        return c

    def _slider(self, lo: int, hi: int, value: int) -> dict:
        wrap = QWidget()
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        label = QLabel(f"{value}%")
        slider.valueChanged.connect(lambda v: label.setText(f"{v}%"))
        h.addWidget(slider, 1)
        h.addWidget(label)
        return {"w": wrap, "slider": slider}

    def _bg_live(self) -> None:
        """Push current background controls into settings and request a redraw."""
        s = self.settings
        s.bg_image = self.bg_image.text().strip()
        s.bg_mode = self.bg_mode.currentText()
        s.bg_opacity = self.bg_opacity["slider"].value()
        s.panel_opacity = self.panel_opacity["slider"].value()
        s.editor_translucent = self.editor_translucent.isChecked()
        self.background_changed.emit()

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose background image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if path:
            self.bg_image.setText(path)

    # ------------------------------------------------------------ save
    def _save(self) -> None:
        s = self.settings
        s.theme = self.theme.currentText()
        s.font_family = self.font_family.currentFont().family()
        s.font_size = self.font_size.value()
        s.bg_image = self.bg_image.text().strip()
        s.bg_mode = self.bg_mode.currentText()
        s.bg_opacity = self.bg_opacity["slider"].value()
        s.panel_opacity = self.panel_opacity["slider"].value()
        s.editor_translucent = self.editor_translucent.isChecked()
        s.tab_width = self.tab_width.value()
        s.autosave = self.autosave.isChecked()
        s.show_line_numbers = self.line_numbers.isChecked()
        s.highlight_current_line = self.caret_line.isChecked()
        s.word_wrap = self.wrap.isChecked()
        s.show_whitespace = self.whitespace.isChecked()
        s.indent_guides = self.guides.isChecked()
        s.show_folding = self.folding.isChecked()
        s.auto_pair = self.auto_pair.isChecked()
        s.error_lens = self.error_lens.isChecked()
        s.git_gutter = self.git_gutter.isChecked()
        s.git_blame = self.git_blame.isChecked()
        s.rainbow_brackets = self.rainbow.isChecked()
        s.sticky_scroll = self.sticky.isChecked()
        s.file_icons = self.file_icons.isChecked()
        s.minimap = self.minimap.isChecked()
        s.breadcrumbs = self.breadcrumbs.isChecked()
        s.python_path = self.python_path.text().strip()
        s.anthropic_api_key = self.anthropic_api_key.text().strip()
        s.clangd_path = self.clangd.text().strip() or "clangd"
        s.omnisharp_path = self.omnisharp.text().strip() or "omnisharp"
        s.save()
        self.saved.emit()
