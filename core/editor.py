"""Code editor built on QScintilla, themed from the active Theme.

Picks a lexer by file extension (C++, C#, Python, JSON, ...), wires up line
numbers, folding, current-line highlight and exposes helpers used by the LSP
client (diagnostics underlining, position <-> offset conversion).
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QColor, QFont
from PyQt6.Qsci import (
    QsciScintilla,
    QsciLexerCPP,
    QsciLexerCSharp,
    QsciLexerPython,
    QsciLexerJSON,
    QsciLexerMarkdown,
    QsciLexerJavaScript,
)

# file extension -> (lexer class, language label)
LEXER_MAP = {
    ".cpp": (QsciLexerCPP, "C++"),
    ".cxx": (QsciLexerCPP, "C++"),
    ".cc": (QsciLexerCPP, "C++"),
    ".c": (QsciLexerCPP, "C"),
    ".h": (QsciLexerCPP, "C/C++ Header"),
    ".hpp": (QsciLexerCPP, "C++ Header"),
    ".cs": (QsciLexerCSharp, "C#"),
    ".py": (QsciLexerPython, "Python"),
    ".json": (QsciLexerJSON, "JSON"),
    ".md": (QsciLexerMarkdown, "Markdown"),
    ".js": (QsciLexerJavaScript, "JavaScript"),
    ".ts": (QsciLexerJavaScript, "TypeScript"),
}

# indicator number used to underline diagnostics
ERROR_INDICATOR = 8
WARNING_INDICATOR = 9

# git gutter marker ids (shown in a dedicated margin)
GIT_ADD = 5
GIT_MOD = 6
GIT_DEL = 7
_GIT_MASK = (1 << GIT_ADD) | (1 << GIT_MOD) | (1 << GIT_DEL)

# rainbow-bracket indicators (one per nesting depth, cycled)
RAINBOW_BASE = 16
RAINBOW_COLORS = ["#ffd700", "#da70d6", "#179fff", "#f8c555", "#a6e3a1", "#ff7eb6"]
_MAX_RAINBOW_CHARS = 200_000


class CodeEditor(QsciScintilla):
    def __init__(self, theme=None, font_family="JetBrains Mono", font_size=13):
        super().__init__()
        self.language = "Plain Text"
        self._font_family = font_family
        self._font_size = font_size
        self._lexer = None
        self._bg_alpha = 255      # < 255 => translucent paper over a backdrop
        self.auto_pair = True
        self._ann_err = None      # QsciStyle for Error Lens (lazy)
        self._ann_warn = None
        self._paper_color = QColor("#1e1e2e")

        self.setUtf8(True)
        # multiple cursors / selections
        self.SendScintilla(QsciScintilla.SCI_SETMULTIPLESELECTION, 1)
        self.SendScintilla(QsciScintilla.SCI_SETADDITIONALSELECTIONTYPING, 1)
        self.SendScintilla(QsciScintilla.SCI_SETMULTIPASTE, 1)
        self.setIndentationsUseTabs(False)
        self.setTabWidth(4)
        self.setAutoIndent(True)
        self.setBackspaceUnindents(True)
        self.setCaretLineVisible(True)
        self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.setMarginLineNumbers(0, True)
        self.setMarginWidth(0, "0000")
        self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setAutoCompletionThreshold(2)
        self.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)

        # breakpoint / diagnostic margin (markers 1, 2)
        self.setMarginType(1, QsciScintilla.MarginType.SymbolMargin)
        self.setMarginWidth(1, 14)
        self.setMarginSensitivity(1, True)
        self.setMarginMarkerMask(1, (1 << 1) | (1 << 2))
        self.markerDefine(QsciScintilla.MarkerSymbol.Circle, 1)
        self.setMarkerBackgroundColor(QColor("#f38ba8"), 1)

        # git gutter margin (markers GIT_ADD/MOD/DEL)
        self.setMarginType(2, QsciScintilla.MarginType.SymbolMargin)
        self.setMarginWidth(2, 5)
        self.setMarginSensitivity(2, False)
        self.setMarginMarkerMask(2, _GIT_MASK)
        for mid, color in ((GIT_ADD, "#3fb950"), (GIT_MOD, "#d29922"),
                           (GIT_DEL, "#f85149")):
            self.markerDefine(QsciScintilla.MarkerSymbol.LeftRectangle, mid)
            self.setMarkerBackgroundColor(QColor(color), mid)
            self.setMarkerForegroundColor(QColor(color), mid)

        # Error Lens annotations rendered indented under the line
        self.setAnnotationDisplay(QsciScintilla.AnnotationDisplay.AnnotationIndented)

        # rainbow bracket indicators (colour the bracket glyph by depth)
        for i, color in enumerate(RAINBOW_COLORS):
            ind = RAINBOW_BASE + i
            self.indicatorDefine(
                QsciScintilla.IndicatorStyle.TextColorIndicator, ind)
            self.setIndicatorForegroundColor(QColor(color), ind)
        self.rainbow_enabled = True

        self.indicatorDefine(QsciScintilla.IndicatorStyle.SquiggleIndicator, ERROR_INDICATOR)
        self.setIndicatorForegroundColor(QColor("#f38ba8"), ERROR_INDICATOR)
        self.indicatorDefine(QsciScintilla.IndicatorStyle.SquiggleIndicator, WARNING_INDICATOR)
        self.setIndicatorForegroundColor(QColor("#f9e2af"), WARNING_INDICATOR)

        if theme is not None:
            self.apply_theme(theme)

    # ------------------------------------------------------------------ lexer
    def set_language_for(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        lexer_cls, label = LEXER_MAP.get(ext, (None, "Plain Text"))
        self.language = label
        if lexer_cls is None:
            self.setLexer(None)
            self._lexer = None
        else:
            lexer = lexer_cls(self)
            lexer.setFont(QFont(self._font_family, self._font_size))
            self.setLexer(lexer)
            self._lexer = lexer
        return label

    # ------------------------------------------------------------ preferences
    def apply_preferences(self, settings) -> None:
        """Apply user-configurable editor options from Settings."""
        self.setTabWidth(int(getattr(settings, "tab_width", 4)))
        show_ln = bool(getattr(settings, "show_line_numbers", True))
        self.setMarginLineNumbers(0, show_ln)
        self.setMarginWidth(0, "0000" if show_ln else 0)
        self.setCaretLineVisible(bool(getattr(settings, "highlight_current_line", True)))
        self.setWrapMode(
            QsciScintilla.WrapMode.WrapWord if getattr(settings, "word_wrap", False)
            else QsciScintilla.WrapMode.WrapNone
        )
        ws = getattr(settings, "show_whitespace", False)
        self.setWhitespaceVisibility(
            QsciScintilla.WhitespaceVisibility.WsVisible if ws
            else QsciScintilla.WhitespaceVisibility.WsInvisible
        )
        self.setIndentationGuides(bool(getattr(settings, "indent_guides", True)))
        self.auto_pair = bool(getattr(settings, "auto_pair", True))
        self.set_signal_prefs(
            bool(getattr(settings, "error_lens", True)),
            bool(getattr(settings, "git_gutter", True)),
            bool(getattr(settings, "rainbow_brackets", True)),
        )
        if getattr(settings, "show_folding", True):
            self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
        else:
            self.setFolding(QsciScintilla.FoldStyle.NoFoldStyle)

    # ------------------------------------------------------------------ theme
    def apply_theme(self, theme) -> None:
        ui = theme.ui
        font = theme.font
        self._font_family = font.get("family", self._font_family)
        self._font_size = int(font.get("size", self._font_size))
        base_font = QFont(self._font_family, self._font_size)
        self.setFont(base_font)

        bg = QColor(ui.get("background", "#1e1e2e"))
        self._paper_color = QColor(ui.get("background", "#1e1e2e"))
        bg.setAlpha(self._bg_alpha)
        fg = QColor(ui.get("text_primary", "#cdd6f4"))
        margin_bg = QColor(ui.get("surface", "#181825"))
        margin_bg.setAlpha(self._bg_alpha)
        margin_fg = QColor(ui.get("text_secondary", "#6c7086"))
        line_hl = QColor(ui.get("line_highlight", "#ffffff10"))
        selection = QColor(ui.get("selection", "#45475a"))

        self.setPaper(bg)
        self.setColor(fg)
        self.setCaretLineBackgroundColor(line_hl)
        self.setCaretForegroundColor(fg)
        self.setMarginsBackgroundColor(margin_bg)
        self.setMarginsForegroundColor(margin_fg)
        self.setSelectionBackgroundColor(selection)
        self.setFoldMarginColors(margin_bg, margin_bg)
        # active bracket pair highlight
        accent = QColor(ui.get("accent", "#89b4fa"))
        self.setMatchedBraceForegroundColor(accent)
        self.setMatchedBraceBackgroundColor(QColor(ui.get("selection", "#45475a")))
        self.setUnmatchedBraceForegroundColor(QColor("#f38ba8"))
        self._apply_translucency()
        self._sync_annotation_paper()

        if self._lexer is not None:
            self._recolor_lexer(theme)

    def set_translucent(self, alpha: int) -> None:
        """alpha 0..255 for the editor paper (255 = solid). Re-apply theme after."""
        self._bg_alpha = max(0, min(255, alpha))

    def _apply_translucency(self) -> None:
        # NOTE: when a wallpaper is active the global QSS sets
        # `QWidget { background: transparent }`, which the editor viewport would
        # inherit. So we must set the editor background EXPLICITLY in both states
        # (transparent to show the wallpaper, or an opaque colour to hide it).
        if self._bg_alpha < 255:
            self.setStyleSheet("QsciScintilla { background: transparent; }")
            self.viewport().setAutoFillBackground(False)
        else:
            hexc = QColor(self._paper_color).name()
            self.setStyleSheet(f"QsciScintilla {{ background: {hexc}; }}")
            self.viewport().setAutoFillBackground(True)
        self.recolor()
        self.viewport().update()

    def _recolor_lexer(self, theme) -> None:
        lexer = self._lexer
        syntax = theme.syntax
        ui = theme.ui
        bg = QColor(ui.get("background", "#1e1e2e"))
        bg.setAlpha(self._bg_alpha)
        default = QColor(ui.get("text_primary", "#cdd6f4"))

        lexer.setDefaultPaper(bg)
        lexer.setDefaultColor(default)
        # paint every style's background so there are no light gaps
        for style in range(128):
            lexer.setPaper(bg, style)
            lexer.setFont(QFont(self._font_family, self._font_size), style)

        mapping = self._style_mapping(lexer, syntax)
        for style, color in mapping.items():
            if color:
                lexer.setColor(QColor(color), style)

    def _style_mapping(self, lexer, syntax: dict) -> dict[int, str]:
        """Map theme syntax colours onto QScintilla style constants per lexer."""
        kw = syntax.get("keyword")
        string = syntax.get("string")
        comment = syntax.get("comment")
        number = syntax.get("number")
        typ = syntax.get("type")
        func = syntax.get("function")
        pre = syntax.get("preprocessor")
        op = syntax.get("operator")

        if isinstance(lexer, (QsciLexerCPP,)):
            return {
                QsciLexerCPP.Keyword: kw,
                QsciLexerCPP.KeywordSet2: typ,
                QsciLexerCPP.Comment: comment,
                QsciLexerCPP.CommentLine: comment,
                QsciLexerCPP.CommentDoc: comment,
                QsciLexerCPP.DoubleQuotedString: string,
                QsciLexerCPP.SingleQuotedString: string,
                QsciLexerCPP.Number: number,
                QsciLexerCPP.PreProcessor: pre,
                QsciLexerCPP.Operator: op,
                QsciLexerCPP.GlobalClass: typ,
            }
        if isinstance(lexer, QsciLexerCSharp):
            return {
                QsciLexerCSharp.Keyword: kw,
                QsciLexerCSharp.KeywordSet2: typ,
                QsciLexerCSharp.Comment: comment,
                QsciLexerCSharp.CommentLine: comment,
                QsciLexerCSharp.CommentDoc: comment,
                QsciLexerCSharp.DoubleQuotedString: string,
                QsciLexerCSharp.Number: number,
                QsciLexerCSharp.PreProcessor: pre,
                QsciLexerCSharp.Operator: op,
            }
        if isinstance(lexer, QsciLexerPython):
            return {
                QsciLexerPython.Keyword: kw,
                QsciLexerPython.ClassName: typ,
                QsciLexerPython.FunctionMethodName: func,
                QsciLexerPython.Comment: comment,
                QsciLexerPython.DoubleQuotedString: string,
                QsciLexerPython.SingleQuotedString: string,
                QsciLexerPython.TripleDoubleQuotedString: string,
                QsciLexerPython.Number: number,
                QsciLexerPython.Operator: op,
                QsciLexerPython.Decorator: pre,
            }
        if isinstance(lexer, QsciLexerJSON):
            return {
                QsciLexerJSON.Keyword: kw,
                QsciLexerJSON.Property: typ,
                QsciLexerJSON.String: string,
                QsciLexerJSON.Number: number,
                QsciLexerJSON.Operator: op,
            }
        if isinstance(lexer, QsciLexerJavaScript):
            return {
                QsciLexerJavaScript.Keyword: kw,
                QsciLexerJavaScript.Comment: comment,
                QsciLexerJavaScript.CommentLine: comment,
                QsciLexerJavaScript.DoubleQuotedString: string,
                QsciLexerJavaScript.SingleQuotedString: string,
                QsciLexerJavaScript.Number: number,
                QsciLexerJavaScript.Operator: op,
            }
        return {}

    # ------------------------------------------------------------ diagnostics
    def clear_diagnostics(self) -> None:
        for ind in (ERROR_INDICATOR, WARNING_INDICATOR):
            self.clearIndicatorRange(
                0, 0, self.lines() - 1, len(self.text(self.lines() - 1)), ind
            )
        self.markerDeleteAll(2)
        self.clearAnnotations()

    def add_diagnostic(self, line: int, col: int, length: int, severity: int) -> None:
        """severity: 1 = error, 2 = warning (LSP DiagnosticSeverity)."""
        indicator = ERROR_INDICATOR if severity == 1 else WARNING_INDICATOR
        self.fillIndicatorRange(line, col, line, col + max(length, 1), indicator)

    # ------------------------------------------------------------ Error Lens
    def _ensure_annotation_styles(self) -> None:
        from PyQt6.Qsci import QsciStyle
        if self._ann_err is None:
            self._ann_err = QsciStyle()
            self._ann_err.setColor(QColor("#f38ba8"))
            self._ann_warn = QsciStyle()
            self._ann_warn.setColor(QColor("#f9e2af"))
            self._sync_annotation_paper()

    def _sync_annotation_paper(self) -> None:
        if self._ann_err is None:
            return
        bg = QColor(self._paper_color)
        bg.setAlpha(255)
        font = QFont(self._font_family, max(self._font_size - 1, 8))
        for style in (self._ann_err, self._ann_warn):
            style.setPaper(bg)
            style.setFont(font)

    def set_error_lens(self, items: list[tuple[int, int, str]]) -> None:
        """items: list of (line, severity, message). severity 1=error 2=warning."""
        self.clearAnnotations()
        if not getattr(self, "error_lens_enabled", True):
            return
        self._ensure_annotation_styles()
        # merge multiple messages per line; worst severity wins the colour
        by_line: dict[int, list[tuple[int, str]]] = {}
        for line, severity, message in items:
            by_line.setdefault(line, []).append((severity, message))
        for line, msgs in by_line.items():
            if line < 0 or line >= self.lines():
                continue
            severity = min(s for s, _ in msgs)
            text = "   ".join(m.strip() for _s, m in msgs)
            prefix = "●  " if severity == 1 else "▲  "
            style = self._ann_err if severity == 1 else self._ann_warn
            self.annotate(line, prefix + text, style)

    # ------------------------------------------------------------ git gutter
    def set_git_markers(self, status_map: dict[int, str]) -> None:
        self.clear_git_markers()
        if not getattr(self, "git_gutter_enabled", True):
            return
        kind = {"added": GIT_ADD, "modified": GIT_MOD, "deleted": GIT_DEL}
        for line, status in status_map.items():
            mid = kind.get(status)
            if mid is not None and 0 <= line < self.lines():
                self.markerAdd(line, mid)

    def clear_git_markers(self) -> None:
        for mid in (GIT_ADD, GIT_MOD, GIT_DEL):
            self.markerDeleteAll(mid)

    # ------------------------------------------------------------ rainbow
    def colorize_brackets(self) -> None:
        last_line = max(self.lines() - 1, 0)
        last_col = len(self.text(last_line))
        for i in range(len(RAINBOW_COLORS)):
            self.clearIndicatorRange(0, 0, last_line, last_col, RAINBOW_BASE + i)
        if not getattr(self, "rainbow_enabled", True):
            return
        text = self.text()
        if len(text) > _MAX_RAINBOW_CHARS:
            return
        pairs = {")": "(", "]": "[", "}": "{"}
        opens = set("([{")
        stack: list[int] = []
        line = 0
        col = 0
        n = len(RAINBOW_COLORS)
        for ch in text:
            if ch == "\n":
                line += 1
                col = 0
                continue
            if ch in opens:
                depth = len(stack) % n
                self.fillIndicatorRange(line, col, line, col + 1, RAINBOW_BASE + depth)
                stack.append(depth)
                col += 1
                continue
            if ch in pairs and stack:
                depth = stack.pop()
                self.fillIndicatorRange(line, col, line, col + 1, RAINBOW_BASE + depth)
                col += 1
                continue
            col += 1

    def set_signal_prefs(self, error_lens: bool, git_gutter: bool,
                         rainbow: bool = True) -> None:
        self.error_lens_enabled = error_lens
        self.git_gutter_enabled = git_gutter
        self.rainbow_enabled = rainbow
        self.setMarginWidth(2, 5 if git_gutter else 0)
        if not error_lens:
            self.clearAnnotations()
        if not git_gutter:
            self.clear_git_markers()
        self.colorize_brackets()

    # ------------------------------------------------------------ positioning
    def goto_line(self, line: int, col: int = 0) -> None:
        self.setCursorPosition(max(line, 0), max(col, 0))
        self.ensureLineVisible(max(line, 0))
        self.setFocus()

    # ------------------------------------------------------------ view tweaks
    def toggle_word_wrap(self) -> bool:
        wrapped = self.wrapMode() != QsciScintilla.WrapMode.WrapNone
        self.setWrapMode(
            QsciScintilla.WrapMode.WrapNone if wrapped else QsciScintilla.WrapMode.WrapWord
        )
        return not wrapped

    def zoom_in(self) -> None:
        self.zoomIn()

    def zoom_out(self) -> None:
        self.zoomOut()

    def zoom_reset(self) -> None:
        self.zoomTo(0)

    # ------------------------------------------------------------ commenting
    _COMMENT_TOKEN = {
        "C++": "//", "C": "//", "C/C++ Header": "//", "C++ Header": "//",
        "C#": "//", "JavaScript": "//", "TypeScript": "//",
        "Python": "#",
    }

    def toggle_comment(self) -> None:
        token = self._COMMENT_TOKEN.get(self.language)
        if token is None:
            return
        if self.hasSelectedText():
            start_line, _s, end_line, end_col = self.getSelection()
            if end_col == 0 and end_line > start_line:
                end_line -= 1
        else:
            start_line, _ = self.getCursorPosition()
            end_line = start_line

        lines = [self.text(ln) for ln in range(start_line, end_line + 1)]
        stripped = [ln for ln in lines if ln.strip()]
        all_commented = stripped and all(
            ln.lstrip().startswith(token) for ln in stripped
        )

        self.beginUndoAction()
        for ln in range(start_line, end_line + 1):
            content = self.text(ln)
            if not content.strip():
                continue
            indent = len(content) - len(content.lstrip())
            if all_commented:
                rest = content[indent:]
                if rest.startswith(token + " "):
                    rest = rest[len(token) + 1:]
                elif rest.startswith(token):
                    rest = rest[len(token):]
                new = content[:indent] + rest
            else:
                new = content[:indent] + token + " " + content[indent:]
            self.setSelection(ln, 0, ln, len(content))
            self.replaceSelectedText(new)
        self.endUndoAction()

    # ------------------------------------------------------------ search
    def find(self, text: str, *, regex=False, case=False, whole=False,
             forward=True, wrap=True) -> bool:
        if not text:
            return False
        line, col = self.getCursorPosition()
        return self.findFirst(
            text, regex, case, whole, wrap, forward, line, col, True
        )

    def replace_current(self, replacement: str) -> None:
        if self.hasSelectedText():
            self.replace(replacement)

    def replace_all(self, text: str, replacement: str, *,
                    regex=False, case=False, whole=False) -> int:
        if not text:
            return 0
        count = 0
        self.beginUndoAction()
        self.setCursorPosition(0, 0)
        found = self.findFirst(text, regex, case, whole, False, True, 0, 0, True)
        while found:
            self.replace(replacement)
            count += 1
            found = self.findNext()
        self.endUndoAction()
        return count

    # ------------------------------------------------------------ completion
    def current_word_prefix(self) -> str:
        line, col = self.getCursorPosition()
        text = self.text(line)[:col]
        i = len(text)
        while i > 0 and (text[i - 1].isalnum() or text[i - 1] in "_"):
            i -= 1
        return text[i:col]

    def show_completions(self, items: list[str]) -> None:
        if not items:
            return
        prefix_len = len(self.current_word_prefix())
        # QScintilla's autocomplete list is space-separated; identifiers only
        clean = sorted({it for it in items if it and " " not in it})
        if not clean:
            return
        self.SendScintilla(QsciScintilla.SCI_AUTOCSETSEPARATOR, ord(" "))
        self.SendScintilla(
            QsciScintilla.SCI_AUTOCSHOW, prefix_len, " ".join(clean).encode("utf-8")
        )

    # ------------------------------------------------------------ power edits
    def duplicate_line(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_LINEDUPLICATE)

    def move_line_up(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_MOVESELECTEDLINESUP)

    def move_line_down(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_MOVESELECTEDLINESDOWN)

    def select_next_occurrence(self) -> None:
        """Multi-cursor: add the next occurrence of the current word/selection."""
        if not self.hasSelectedText():
            self.SendScintilla(QsciScintilla.SCI_SETSELECTIONMODE, 0)
            # select current word first
            pos = self.SendScintilla(QsciScintilla.SCI_GETCURRENTPOS)
            start = self.SendScintilla(QsciScintilla.SCI_WORDSTARTPOSITION, pos, 1)
            end = self.SendScintilla(QsciScintilla.SCI_WORDENDPOSITION, pos, 1)
            self.SendScintilla(QsciScintilla.SCI_SETSELECTION, end, start)
            return
        self.SendScintilla(QsciScintilla.SCI_TARGETWHOLEDOCUMENT)
        self.SendScintilla(QsciScintilla.SCI_MULTIPLESELECTADDNEXT)

    # ------------------------------------------------------------ auto-pair
    _OPEN_PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}

    def keyPressEvent(self, event):  # noqa: N802
        text = event.text()
        if self.auto_pair and text in self._OPEN_PAIRS:
            close = self._OPEN_PAIRS[text]
            if self.hasSelectedText():
                sel = self.selectedText()
                self.replaceSelectedText(f"{text}{sel}{close}")
                return
            super().keyPressEvent(event)
            line, col = self.getCursorPosition()
            self.insertAt(close, line, col)
            return
        super().keyPressEvent(event)
