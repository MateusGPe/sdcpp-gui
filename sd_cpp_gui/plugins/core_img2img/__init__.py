from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Optional

from sd_cpp_gui.domain.plugins.interface import IPlugin
from sd_cpp_gui.plugins.core_img2img.panel import Img2ImgSection

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer


class Img2ImgPlugin(IPlugin):
    """Plugin for the Img2Img panel."""

    def __init__(self) -> None:
        """Logic: Initializes plugin."""
        self._container: Optional[DependencyContainer] = None

    @property
    def manifest(self) -> Dict[str, Any]:
        """Logic: Returns manifest."""
        return {
            "name": "Image to Image",
            "key": "img2img",
            "version": "1.0.0",
            "description": "Panel for Image-to-Image generation.",
            "icon": "🖼️",
        }

    def initialize(self, container: DependencyContainer) -> None:
        """Logic: Injects container."""
        self._container = container

    def create_ui(self, parent: tk.Widget) -> Optional[tk.Widget]:
        """Logic: Creates UI."""
        if not self._container:
            raise RuntimeError("Img2ImgPlugin not initialized")
        return Img2ImgSection(parent, self._container.state_manager)
