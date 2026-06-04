"""Code snippets/templates with simple placeholder support.

A snippet body may contain ``${1:default}`` / ``${2}`` placeholders and a final
``$0`` caret marker. :func:`expand` strips the markers to a plain string and
returns the caret offset so the editor can position the cursor there.

Built-in snippets ship per language; users can add their own in
``~/.neode/snippets.json`` as ``{ "<language>": { "<prefix>": "<body>" } }``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_PLACEHOLDER_DEFAULT = re.compile(r"\$\{\d+:([^}]*)\}")
_PLACEHOLDER_EMPTY = re.compile(r"\$\{\d+\}")

BUILTIN: dict[str, dict[str, str]] = {
    "Python": {
        "def": "def ${1:name}(${2:args}):\n\t$0",
        "class": "class ${1:Name}:\n\tdef __init__(self):\n\t\t$0",
        "main": 'if __name__ == "__main__":\n\t$0',
        "for": "for ${1:item} in ${2:iterable}:\n\t$0",
        "try": "try:\n\t$0\nexcept ${1:Exception} as e:\n\tpass",
    },
    "C++": {
        "main": "#include <iostream>\n\nint main() {\n\t$0\n\treturn 0;\n}",
        "for": "for (int ${1:i} = 0; ${1:i} < ${2:n}; ++${1:i}) {\n\t$0\n}",
        "class": "class ${1:Name} {\npublic:\n\t$0\n};",
    },
    "C#": {
        "main": "using System;\n\nclass Program {\n\tstatic void Main() {\n\t\t$0\n\t}\n}",
        "for": "for (int ${1:i} = 0; ${1:i} < ${2:n}; ${1:i}++) {\n\t$0\n}",
        "prop": "public ${1:int} ${2:Name} { get; set; }$0",
    },
    "JavaScript": {
        "func": "function ${1:name}(${2:args}) {\n\t$0\n}",
        "log": "console.log($0);",
        "for": "for (let ${1:i} = 0; ${1:i} < ${2:n}; ${1:i}++) {\n\t$0\n}",
    },
}
# aliases
BUILTIN["C"] = BUILTIN["C++"]
BUILTIN["TypeScript"] = BUILTIN["JavaScript"]


def expand(body: str) -> tuple[str, int]:
    """Return (clean_text, caret_offset) for a snippet body."""
    text = _PLACEHOLDER_DEFAULT.sub(r"\1", body)
    text = _PLACEHOLDER_EMPTY.sub("", text)
    idx = text.find("$0")
    if idx >= 0:
        text = text[:idx] + text[idx + 2:]
        return text, idx
    return text, len(text)


def for_language(language: str, user_dir: Path | None = None) -> dict[str, str]:
    """Built-in + user snippets for a language."""
    out = dict(BUILTIN.get(language, {}))
    path = (user_dir or (Path.home() / ".neode")) / "snippets.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.update(data.get(language, {}))
        except (json.JSONDecodeError, OSError):
            pass
    return out
