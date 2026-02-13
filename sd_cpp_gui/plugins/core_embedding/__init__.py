from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Optional

from sd_cpp_gui.domain.plugins.interface import IPlugin
from sd_cpp_gui.plugins.core_embedding.panel import EmbeddingSection

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer


class EmbeddingPlugin(IPlugin):
    """Plugin for the Embedding selection panel."""

    def __init__(self) -> None:
        """Logic: Initializes plugin."""
        self._container: Optional[DependencyContainer] = None

    @property
    def manifest(self) -> Dict[str, Any]:
        """Logic: Returns manifest."""
        return {
            "name": "Embeddings",
            "key": "embedding",
            "version": "1.0.0",
            "description": "Panel for Embedding/Textual Inversion management.",
            "icon": "🧩",
        }

    def initialize(self, container: DependencyContainer) -> None:
        """Logic: Injects container."""
        self._container = container

    def create_ui(self, parent: tk.Widget) -> Optional[tk.Widget]:
        """Logic: Creates UI."""
        if not self._container:
            raise RuntimeError("EmbeddingPlugin not initialized")
        on_change_callback = getattr(
            self._container, "on_network_param_change", None
        )
        return EmbeddingSection(
            parent, self._container.embeddings, on_change_callback
        )
