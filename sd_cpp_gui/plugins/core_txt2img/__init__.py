from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Optional

from sd_cpp_gui.domain.plugins.interface import IPlugin
from sd_cpp_gui.plugins.core_txt2img.panel import GeneralPanel

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer


class Txt2ImgPlugin(IPlugin):
    """
    Core Plugin that provides the main "General" Text-to-Image panel.
    """

    def __init__(self) -> None:
        """Logic: Initializes plugin."""
        self._container: Optional[DependencyContainer] = None

    @property
    def manifest(self) -> Dict[str, Any]:
        """Logic: Returns plugin manifest."""
        return {
            "name": "General",
            "key": "general",
            "version": "1.0.0",
            "description": "Core Text-to-Image Generation Panel",
            "icon": "🏠",
        }

    def initialize(self, container: DependencyContainer) -> None:
        """Logic: Injects container."""
        self._container = container

    def create_ui(self, parent: tk.Widget) -> Optional[tk.Widget]:
        """Logic: Creates UI panel."""
        if not self._container:
            raise RuntimeError("Txt2ImgPlugin not initialized")
        return GeneralPanel(
            parent,
            self._container,
        )
