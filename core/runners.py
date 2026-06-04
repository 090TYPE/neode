"""Maps a source file to a shell command that builds and/or runs it.

Returns a single command string using ``&&`` to chain compile + execute, which
works in both cmd.exe and bash. The Terminal wraps it in the platform shell.
"""
from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

# explicit interpreter override (set from settings.python_path)
PYTHON_OVERRIDE = ""
_PYTHON_CACHE: str | None = None


def _q(text: str) -> str:
    return f'"{text}"'


def _is_store_stub(path: str | None) -> bool:
    """The Microsoft Store 'python' alias that only prints an error."""
    return bool(path) and "WindowsApps" in path


def _venv_python(start_dir: str | None) -> str | None:
    """Walk up from start_dir looking for a project virtual-env interpreter."""
    if not start_dir:
        return None
    rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    d = Path(start_dir)
    for _ in range(5):
        for name in (".venv", "venv", "env"):
            cand = d / name / rel
            if cand.exists():
                return str(cand)
        if d.parent == d:
            break
        d = d.parent
    return None


def find_python(start_dir: str | None = None) -> str:
    """Resolve a usable Python interpreter, preferring a project venv.

    Order: explicit override → project venv → real system Python (skipping the
    Microsoft Store stub) → common install dirs → bare 'python'.
    """
    global _PYTHON_CACHE
    if PYTHON_OVERRIDE:
        return _q(PYTHON_OVERRIDE) if " " in PYTHON_OVERRIDE else PYTHON_OVERRIDE

    venv = _venv_python(start_dir)
    if venv:
        return _q(venv)

    if _PYTHON_CACHE:
        return _PYTHON_CACHE

    found = None
    which = shutil.which("python")
    if which and not _is_store_stub(which):
        found = which
    if found is None and os.name == "nt":
        base = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python")
        matches = sorted(glob.glob(os.path.join(base, "Python3*", "python.exe")),
                         reverse=True)
        for exe in matches + [r"C:\Python313\python.exe",
                              r"C:\Python312\python.exe",
                              r"C:\Python311\python.exe"]:
            if os.path.exists(exe):
                found = exe
                break
    if found is None and os.name != "nt":
        found = shutil.which("python3")

    _PYTHON_CACHE = _q(found) if found and " " in found else (found or "python")
    return _PYTHON_CACHE


# simple interpreters: ext -> command template using {name}
_INTERPRETED = {
    ".py":  "python {name}",
    ".pyw": "python {name}",
    ".js":  "node {name}",
    ".mjs": "node {name}",
    ".cjs": "node {name}",
    ".ts":  "npx ts-node {name}",
    ".go":  "go run {name}",
    ".rb":  "ruby {name}",
    ".php": "php {name}",
    ".pl":  "perl {name}",
    ".lua": "lua {name}",
    ".sh":  "bash {name}",
    ".bash": "bash {name}",
    ".ps1": "powershell -ExecutionPolicy Bypass -File {name}",
    ".r":   "Rscript {name}",
    ".dart": "dart run {name}",
    ".groovy": "groovy {name}",
}

# every extension we know how to run (for UI hints)
RUNNABLE = set(_INTERPRETED) | {
    ".cpp", ".cc", ".cxx", ".c++", ".c", ".rs", ".java", ".cs", ".kt", ".swift",
}

# plugins can register extra runners: ext -> command template using {name}
EXTRA_RUNNERS: dict[str, str] = {}


def build_command(file_path: str) -> str | None:
    """Return a shell command to run *file_path*, or None if unknown."""
    path = Path(file_path)
    ext = path.suffix.lower()
    name = _q(path.name)
    stem = path.stem
    win = os.name == "nt"
    exe = stem + (".exe" if win else "")
    run_exe = _q(exe) if win else f'"./{exe}"'

    if ext in EXTRA_RUNNERS:
        return EXTRA_RUNNERS[ext].format(name=name, stem=_q(stem), exe=_q(exe))
    if ext in (".py", ".pyw"):
        return f"{find_python(str(path.parent))} {name}"
    if ext in _INTERPRETED:
        return _INTERPRETED[ext].format(name=name)

    if ext in (".cpp", ".cc", ".cxx", ".c++"):
        return f"g++ -std=c++17 -O2 -o {_q(exe)} {name} && {run_exe}"
    if ext == ".c":
        return f"gcc -O2 -o {_q(exe)} {name} && {run_exe}"
    if ext == ".rs":
        return f"rustc -O -o {_q(exe)} {name} && {run_exe}"
    if ext == ".java":
        return f"javac {name} && java {_q(stem)}"
    if ext == ".kt":
        jar = _q(stem + ".jar")
        return f"kotlinc {name} -include-runtime -d {jar} && java -jar {jar}"
    if ext == ".swift":
        return f"swift {name}"
    if ext == ".cs":
        return "dotnet run"
    return None


def language_label(file_path: str) -> str:
    return Path(file_path).suffix.lower().lstrip(".").upper() or "file"
