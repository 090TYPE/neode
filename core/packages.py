"""Package-manager registry: install/uninstall/list libraries for many languages.

Each Manager holds command *templates* with two placeholders:
    {py}   -> a resolved Python interpreter (for pip; uses the project venv)
    {pkg}  -> the package name (quoted if it contains spaces)

The UI builds a concrete command via :func:`build` and runs it in the
integrated terminal, so output streams live and pip uses the project's venv.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.runners import find_python


@dataclass(frozen=True)
class Manager:
    id: str
    label: str
    manifests: tuple[str, ...]      # files that mark a project of this type
    install: str
    uninstall: str
    list: str
    install_all: str                # install everything from the manifest
    install_all_label: str = "Install from manifest"


MANAGERS: dict[str, Manager] = {
    "pip": Manager(
        "pip", "Python · pip", ("requirements.txt", "pyproject.toml", "setup.py", "Pipfile"),
        install="{py} -m pip install {pkg}",
        uninstall="{py} -m pip uninstall -y {pkg}",
        list="{py} -m pip list",
        install_all="{py} -m pip install -r requirements.txt",
        install_all_label="pip install -r requirements.txt",
    ),
    "npm": Manager(
        "npm", "Node · npm", ("package.json",),
        install="npm install {pkg}",
        uninstall="npm uninstall {pkg}",
        list="npm list --depth=0",
        install_all="npm install",
        install_all_label="npm install",
    ),
    "yarn": Manager(
        "yarn", "Node · yarn", ("yarn.lock",),
        install="yarn add {pkg}",
        uninstall="yarn remove {pkg}",
        list="yarn list --depth=0",
        install_all="yarn install",
        install_all_label="yarn install",
    ),
    "cargo": Manager(
        "cargo", "Rust · cargo", ("Cargo.toml",),
        install="cargo add {pkg}",
        uninstall="cargo remove {pkg}",
        list="cargo tree --depth 1",
        install_all="cargo build",
        install_all_label="cargo build",
    ),
    "go": Manager(
        "go", "Go · go get", ("go.mod",),
        install="go get {pkg}",
        uninstall="go get {pkg}@none",
        list="go list -m all",
        install_all="go mod download",
        install_all_label="go mod download",
    ),
    "gem": Manager(
        "gem", "Ruby · gem", ("Gemfile", "*.gemspec"),
        install="gem install {pkg}",
        uninstall="gem uninstall {pkg}",
        list="gem list",
        install_all="bundle install",
        install_all_label="bundle install",
    ),
    "composer": Manager(
        "composer", "PHP · composer", ("composer.json",),
        install="composer require {pkg}",
        uninstall="composer remove {pkg}",
        list="composer show",
        install_all="composer install",
        install_all_label="composer install",
    ),
    "dotnet": Manager(
        "dotnet", "C# · .NET", ("*.csproj", "*.sln"),
        install="dotnet add package {pkg}",
        uninstall="dotnet remove package {pkg}",
        list="dotnet list package",
        install_all="dotnet restore",
        install_all_label="dotnet restore",
    ),
    "gradle": Manager(
        "gradle", "Java · gradle", ("build.gradle", "build.gradle.kts"),
        install="",   # gradle deps are edited in build.gradle, not installed ad-hoc
        uninstall="",
        list="gradle dependencies",
        install_all="gradle build",
        install_all_label="gradle build",
    ),
}

# nice ordering for the UI selector
ORDER = ["pip", "npm", "yarn", "cargo", "go", "gem", "composer", "dotnet", "gradle"]


def detect(root: str | None) -> str:
    """Return the manager id that best matches the project at *root*."""
    if not root:
        return "pip"
    base = Path(root)
    for mid in ORDER:
        mgr = MANAGERS[mid]
        for pattern in mgr.manifests:
            if "*" in pattern:
                if any(base.glob(pattern)):
                    return mid
            elif (base / pattern).exists():
                return mid
    return "pip"


def _q(text: str) -> str:
    return f'"{text}"' if " " in text else text


def build(manager_id: str, action: str, root: str | None, pkg: str = "") -> str | None:
    """Build a concrete shell command for an action, or None if unsupported."""
    mgr = MANAGERS.get(manager_id)
    if mgr is None:
        return None
    template = getattr(mgr, action, "")
    if not template:
        return None
    return template.format(py=find_python(root), pkg=_q(pkg.strip()))
