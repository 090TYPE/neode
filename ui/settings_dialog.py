"""Settings dialog — font size, theme, autosave and language-server paths."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QVBoxLayout, QHBoxLayout, QSlider, QComboBox,
    QCheckBox, QLineEdit, QPushButton, QLabel, QSpinBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal


class SettingsDialog(QDialog):
    # emitted after Apply/OK so the window can re-theme / restart autosave
    applied = pyqtSignal()
    edit_theme_requested = pyqtSignal()

    def __init__(self, settings, theme_names: list[str], parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.resize(480, 560)

        form = QFormLayout()

        theme_row = QHBoxLayout()
        self.theme = QComboBox()
        self.theme.addItems(theme_names)
        if settings.theme in theme_names:
            self.theme.setCurrentText(settings.theme)
        edit_theme = QPushButton("Customize…")
        edit_theme.clicked.connect(self._open_theme_editor)
        theme_row.addWidget(self.theme, 1)
        theme_row.addWidget(edit_theme)
        form.addRow("Theme", self._wrap(theme_row))

        size_row = QHBoxLayout()
        self.size = QSlider(Qt.Orientation.Horizontal)
        self.size.setRange(8, 28)
        self.size.setValue(settings.font_size)
        self.size_label = QLabel(str(settings.font_size))
        self.size.valueChanged.connect(lambda v: self.size_label.setText(str(v)))
        size_row.addWidget(self.size)
        size_row.addWidget(self.size_label)
        form.addRow("Font size", self._wrap(size_row))

        self.font_family = QLineEdit(settings.font_family)
        form.addRow("Font family", self.font_family)

        self.autosave = QCheckBox("Save files automatically")
        self.autosave.setChecked(settings.autosave)
        form.addRow("Autosave", self.autosave)

        # ---- editor preferences ----
        form.addRow(self._divider())

        self.tab_width = QSpinBox()
        self.tab_width.setRange(1, 8)
        self.tab_width.setValue(settings.tab_width)
        form.addRow("Tab width", self.tab_width)

        self.line_numbers = QCheckBox("Show line numbers")
        self.line_numbers.setChecked(settings.show_line_numbers)
        form.addRow("", self.line_numbers)

        self.caret_line = QCheckBox("Highlight current line")
        self.caret_line.setChecked(settings.highlight_current_line)
        form.addRow("", self.caret_line)

        self.wrap = QCheckBox("Word wrap")
        self.wrap.setChecked(settings.word_wrap)
        form.addRow("", self.wrap)

        self.whitespace = QCheckBox("Show whitespace")
        self.whitespace.setChecked(settings.show_whitespace)
        form.addRow("", self.whitespace)

        self.guides = QCheckBox("Indentation guides")
        self.guides.setChecked(settings.indent_guides)
        form.addRow("", self.guides)

        self.folding = QCheckBox("Code folding")
        self.folding.setChecked(settings.show_folding)
        form.addRow("", self.folding)

        # ---- language servers ----
        form.addRow(self._divider())
        self.clangd = QLineEdit(settings.clangd_path)
        form.addRow("clangd path", self.clangd)
        self.omnisharp = QLineEdit(settings.omnisharp_path)
        form.addRow("OmniSharp path", self.omnisharp)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self._save_and_close)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addStretch(1)
        root.addLayout(buttons)

    @staticmethod
    def _wrap(layout) -> QLabel:
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        w.setLayout(layout)
        return w

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _open_theme_editor(self) -> None:
        self.edit_theme_requested.emit()

    def _save_and_close(self) -> None:
        self.settings.theme = self.theme.currentText()
        self.settings.font_size = self.size.value()
        self.settings.font_family = self.font_family.text().strip() or "JetBrains Mono"
        self.settings.autosave = self.autosave.isChecked()
        self.settings.tab_width = self.tab_width.value()
        self.settings.show_line_numbers = self.line_numbers.isChecked()
        self.settings.highlight_current_line = self.caret_line.isChecked()
        self.settings.word_wrap = self.wrap.isChecked()
        self.settings.show_whitespace = self.whitespace.isChecked()
        self.settings.indent_guides = self.guides.isChecked()
        self.settings.show_folding = self.folding.isChecked()
        self.settings.clangd_path = self.clangd.text().strip() or "clangd"
        self.settings.omnisharp_path = self.omnisharp.text().strip() or "omnisharp"
        self.settings.save()
        self.applied.emit()
        self.accept()
