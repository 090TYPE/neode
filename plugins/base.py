"""Base class every plugin extends.

A plugin file lives in plugins/ (bundled) or ~/.neode/plugins/ (user) and
defines a class named ``Plugin`` deriving from BasePlugin. The loader
instantiates it with the shared PluginAPI and calls ``activate()`` on enable /
``deactivate()`` on disable.

    from plugins.base import BasePlugin

    class Plugin(BasePlugin):
        name = "My Plugin"
        version = "1.0.0"
        author = "you"
        description = "What it does."

        def activate(self):
            self.api.ui.register_command("Say Hi", self.hi)

        def hi(self):
            self.api.ui.show_notification("Hello!")
"""
from __future__ import annotations


class BasePlugin:
    name = "Unnamed Plugin"
    version = "1.0.0"
    author = ""
    description = ""

    def __init__(self, api):
        self.api = api  # access to editor, terminal, ui, statusbar, events, …
        # convenient per-plugin persisted store
        self.storage = api.storage(self.name)

    def activate(self) -> None:
        """Called when the plugin is enabled."""

    def deactivate(self) -> None:
        """Called when the plugin is disabled or reloaded."""
