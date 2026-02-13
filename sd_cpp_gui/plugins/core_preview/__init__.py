from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Optional

from sd_cpp_gui.domain.plugins.interface import IPlugin
from sd_cpp_gui.plugins.core_preview.panel import PreviewPanel

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer


class PreviewPlugin(IPlugin):
    """Core Plugin that provides the main Preview/Console panel."""

    def __init__(self) -> None:
        """Logic: Initializes plugin."""
        self._container: Optional[DependencyContainer] = None
        self.panel: Optional[PreviewPanel] = None

    @property
    def manifest(self) -> Dict[str, Any]:
        """
        This is a 'headless' UI plugin; it doesn't appear in the sidebar
        but is a critical part of the main layout.

        Logic: Returns manifest.
        """
        return {
            "name": "Preview Panel",
            "key": "preview",
            "version": "1.0.0",
            "description": "Core Preview, Console, and Parameter Info Panel.",
            "icon": "",
        }

    def initialize(self, container: DependencyContainer) -> None:
        """Logic: Injects container."""
        self._container = container

    def create_ui(self, parent: tk.Widget) -> Optional[tk.Widget]:
        """Logic: Creates UI."""
        if not self._container:
            raise RuntimeError("PreviewPlugin not initialized")
        self.panel = PreviewPanel(parent, self._container)
        return self.panel
