from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Optional

from sd_cpp_gui.domain.plugins.interface import IPlugin
from sd_cpp_gui.plugins.core_lora.panel import LoraSection

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer


class LoraPlugin(IPlugin):
    """Plugin for the LoRA selection panel."""

    def __init__(self) -> None:
        """Logic: Initializes plugin."""
        self._container: Optional[DependencyContainer] = None

    @property
    def manifest(self) -> Dict[str, Any]:
        """Logic: Returns manifest."""
        return {
            "name": "LoRA",
            "key": "lora",
            "version": "1.0.0",
            "description": "Panel for LoRA selection and management.",
            "icon": "🔗",
        }

    def initialize(self, container: DependencyContainer) -> None:
        """Logic: Injects container."""
        self._container = container

    def create_ui(self, parent: tk.Widget) -> Optional[tk.Widget]:
        """Logic: Creates UI."""
        if not self._container:
            raise RuntimeError("LoraPlugin not initialized")
        on_change_callback = getattr(
            self._container, "on_network_param_change", None
        )
        return LoraSection(parent, self._container.loras, on_change_callback)
