"""Discovers, loads and manages plugins from bundled + user directories.

Each plugin is a ``*.py`` file exporting a ``Plugin`` class. Plugins are loaded
from the bundled ``plugins/`` folder and from the user folder
``~/.neode/plugins/`` so users can drop in their own without touching the repo.

Plugins can be enabled/disabled at runtime; the disabled set is persisted in
settings so the choice survives restarts.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

# framework files that are not plugins
_SKIP = {"__init__.py", "base.py", "loader.py", "api.py"}


@dataclass
class PluginRecord:
    plugin_id: str            # stable id (file stem)
    path: Path
    source: str               # "bundled" or "user"
    name: str = "Unknown"
    version: str = ""
    author: str = ""
    description: str = ""
    cls: type | None = field(default=None, repr=False)
    instance: object | None = field(default=None, repr=False)
    enabled: bool = False
    error: str = ""


class PluginLoader:
    def __init__(self, bundled_dir: Path, api, user_dir: Path | None = None):
        self.bundled_dir = Path(bundled_dir)
        self.user_dir = Path(user_dir) if user_dir else (
            Path.home() / ".neode" / "plugins"
        )
        self.api = api
        self.settings = getattr(api, "settings", None)
        self.records: dict[str, PluginRecord] = {}

    # ------------------------------------------------------------ discovery
    def _disabled(self) -> set[str]:
        if self.settings is not None:
            return set(self.settings.disabled_plugins)
        return set()

    def _persist_disabled(self) -> None:
        if self.settings is None:
            return
        self.settings.disabled_plugins = [
            pid for pid, rec in self.records.items() if not rec.enabled
        ]
        self.settings.save()

    def _iter_files(self):
        for directory, source in ((self.bundled_dir, "bundled"),
                                  (self.user_dir, "user")):
            if not directory.exists():
                continue
            for file in sorted(directory.glob("*.py")):
                if file.name in _SKIP or file.name.startswith("_"):
                    continue
                yield file, source

    def ensure_user_dir(self) -> None:
        """Create the user plugins folder with a short README if it's missing."""
        try:
            self.user_dir.mkdir(parents=True, exist_ok=True)
            readme = self.user_dir / "README.txt"
            if not readme.exists():
                readme.write_text(
                    "Drop NeoIDE plugins here as *.py files.\n\n"
                    "Each plugin defines a class named `Plugin` deriving from\n"
                    "plugins.base.BasePlugin. Set name/version/author/description\n"
                    "class attributes and implement activate()/deactivate().\n"
                    "Manage them from NeoIDE: command palette → 'Manage Plugins'.\n",
                    encoding="utf-8",
                )
        except OSError:
            pass

    def discover(self) -> None:
        """Import all plugin modules and (re)build records, activating enabled ones."""
        self.ensure_user_dir()
        self.unload_all()
        self.records.clear()
        disabled = self._disabled()

        for file, source in self._iter_files():
            plugin_id = file.stem
            record = PluginRecord(plugin_id=plugin_id, path=file, source=source)
            try:
                cls = self._import_class(file)
                if cls is None:
                    continue
                record.cls = cls
                record.name = getattr(cls, "name", plugin_id)
                record.version = getattr(cls, "version", "")
                record.author = getattr(cls, "author", "")
                record.description = getattr(cls, "description", "")
            except Exception as exc:  # broken module
                record.error = str(exc)
                self.records[plugin_id] = record
                self._notify(f"Plugin {file.name} failed to import: {exc}", 4000)
                continue

            self.records[plugin_id] = record
            if plugin_id not in disabled:
                self._activate(record)

    # backwards-compatible alias
    def load_all(self) -> None:
        self.discover()

    def _import_class(self, file: Path):
        mod_name = f"neode_plugin_{file.parent.name}_{file.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, file)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, "Plugin", None)

    # ------------------------------------------------------------ lifecycle
    def _activate(self, record: PluginRecord) -> bool:
        if record.cls is None or record.enabled:
            return False
        try:
            record.instance = record.cls(self.api)
            record.instance.activate()
            record.enabled = True
            record.error = ""
            self._notify(f"Loaded plugin: {record.name}", 1200)
            return True
        except Exception as exc:
            record.error = str(exc)
            record.enabled = False
            self._notify(f"Plugin {record.name} failed: {exc}", 4000)
            return False

    def _deactivate(self, record: PluginRecord) -> None:
        if record.instance is not None:
            try:
                record.instance.deactivate()
            except Exception:
                pass
        record.instance = None
        record.enabled = False

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        record = self.records.get(plugin_id)
        if record is None:
            return
        if enabled and not record.enabled:
            self._activate(record)
        elif not enabled and record.enabled:
            self._deactivate(record)
        self._persist_disabled()

    def reload(self, plugin_id: str) -> None:
        record = self.records.get(plugin_id)
        if record is None:
            return
        was_enabled = record.enabled
        self._deactivate(record)
        try:
            record.cls = self._import_class(record.path)
            record.name = getattr(record.cls, "name", plugin_id)
            record.version = getattr(record.cls, "version", "")
            record.author = getattr(record.cls, "author", "")
            record.description = getattr(record.cls, "description", "")
            record.error = ""
        except Exception as exc:
            record.error = str(exc)
            return
        if was_enabled:
            self._activate(record)

    def unload_all(self) -> None:
        for record in self.records.values():
            self._deactivate(record)

    # ------------------------------------------------------------ helpers
    @property
    def loaded(self) -> list:
        return [r.instance for r in self.records.values() if r.instance is not None]

    def all_records(self) -> list[PluginRecord]:
        return sorted(self.records.values(), key=lambda r: r.name.lower())

    def _notify(self, text: str, msec: int) -> None:
        try:
            self.api.ui.show_notification(text, msec)
        except Exception:
            pass
