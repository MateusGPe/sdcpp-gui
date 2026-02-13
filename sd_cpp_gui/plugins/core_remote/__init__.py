"""
Core Remote Plugin.
"""

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Optional

from sd_cpp_gui.domain.plugins.interface import IPlugin

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer


class RemotePlugin(IPlugin):
    """
    Core Plugin that provides the Remote Model Browser.
    This plugin is 'headless' in the main content area (create_ui returns None),
    but provides a specific method `open_window` triggered by the sidebar.
    """

    def __init__(self) -> None:
        self.container: Optional["DependencyContainer"] = None

    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "key": "remote",
            "name": "Remote Browser",
            "icon": "🌎",
            "version": "1.0.0",
        }

    def initialize(self, container: "DependencyContainer") -> None:
        self.container = container

    def create_ui(self, parent: tk.Widget) -> Optional[tk.Widget]:
        return None

    def open_window(self, parent_app: Any) -> None:
        """Opens the Remote Browser Window."""
        from .window import RemoteBrowserWindow

        RemoteBrowserWindow(parent_app, self.container)
