"""Find & Replace bar docked at the top of the editor area.

Operates on whatever editor is currently active (provided by a getter callback
so the bar never holds a stale reference when tabs switch).
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QToolButton, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence


class FindBar(QWidget):
    def __init__(self, get_editor):
        super().__init__()
        self._get_editor = get_editor
        self.setVisible(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        # --- find row ---
        find_row = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.find_input.returnPressed.connect(self.find_next)
        self.find_input.textChanged.connect(self._on_text_changed)

        self.btn_case = self._toggle("Aa", "Match case")
        self.btn_word = self._toggle("ab", "Whole word")
        self.btn_regex = self._toggle(".*", "Regex")
        self.btn_prev = self._button("▲", "Previous (Shift+F3)", self.find_prev)
        self.btn_next = self._button("▼", "Next (F3)", self.find_next)
        self.status = QLabel("")
        self.status.setStyleSheet("color: #6c7086;")
        self.btn_close = self._button("✕", "Close (Esc)", self.hide_bar)

        find_row.addWidget(self.find_input, 1)
        for w in (self.btn_case, self.btn_word, self.btn_regex,
                  self.btn_prev, self.btn_next, self.status):
            find_row.addWidget(w)
        find_row.addStretch(0)
        find_row.addWidget(self.btn_close)
        root.addLayout(find_row)

        # --- replace row ---
        replace_row = QHBoxLayout()
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace")
        self.replace_input.returnPressed.connect(self.replace_one)
        self.btn_replace = self._button("Replace", "Replace", self.replace_one)
        self.btn_replace_all = self._button("All", "Replace all", self.replace_all)
        replace_row.addWidget(self.replace_input, 1)
        replace_row.addWidget(self.btn_replace)
        replace_row.addWidget(self.btn_replace_all)
        self.replace_widget = QWidget()
        self.replace_widget.setLayout(replace_row)
        root.addWidget(self.replace_widget)

        QShortcut(QKeySequence("Esc"), self.find_input, activated=self.hide_bar)

    # ------------------------------------------------------------ widgets
    def _toggle(self, text: str, tip: str) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(True)
        b.toggled.connect(lambda _c: self._on_text_changed())
        return b

    def _button(self, text: str, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.clicked.connect(slot)
        return b

    # ------------------------------------------------------------ show/hide
    def show_find(self) -> None:
        self.replace_widget.setVisible(False)
        self._show_common()

    def show_replace(self) -> None:
        self.replace_widget.setVisible(True)
        self._show_common()

    def _show_common(self) -> None:
        editor = self._get_editor()
        if editor is not None and editor.hasSelectedText():
            sel = editor.selectedText()
            if "\n" not in sel and " " not in sel:
                self.find_input.setText(sel)
        self.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_bar(self) -> None:
        self.setVisible(False)
        editor = self._get_editor()
        if editor is not None:
            editor.setFocus()

    # ------------------------------------------------------------ operations
    def _opts(self) -> dict:
        return {
            "regex": self.btn_regex.isChecked(),
            "case": self.btn_case.isChecked(),
            "whole": self.btn_word.isChecked(),
        }

    def _on_text_changed(self) -> None:
        # incremental: search from the current position without advancing
        editor = self._get_editor()
        if editor is None or not self.find_input.text():
            self.status.setText("")
            return
        ok = editor.find(self.find_input.text(), forward=True, **self._opts())
        self.status.setText("" if ok else "No results")

    def find_next(self) -> None:
        editor = self._get_editor()
        if editor is None:
            return
        ok = editor.find(self.find_input.text(), forward=True, **self._opts())
        self.status.setText("" if ok else "No results")

    def find_prev(self) -> None:
        editor = self._get_editor()
        if editor is None:
            return
        ok = editor.find(self.find_input.text(), forward=False, **self._opts())
        self.status.setText("" if ok else "No results")

    def replace_one(self) -> None:
        editor = self._get_editor()
        if editor is None:
            return
        editor.replace_current(self.replace_input.text())
        self.find_next()

    def replace_all(self) -> None:
        editor = self._get_editor()
        if editor is None:
            return
        n = editor.replace_all(
            self.find_input.text(), self.replace_input.text(), **self._opts()
        )
        self.status.setText(f"{n} replaced")
