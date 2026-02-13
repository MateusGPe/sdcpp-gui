from typing import Any

from sd_cpp_gui.domain.plugins.interface import IPlugin
from sd_cpp_gui.plugins.core_embedding.panel import EmbeddingSection
from sd_cpp_gui.plugins.core_lora.panel import LoraSection


class LoraPlugin(IPlugin):
    def initialize(self, container: Any) -> None:
        """Logic: Sets up the plugin by injecting dependencies (lora manager,
        state manager) from the container"""
        self.container = container
        self.lora_manager = container.loras
        self.state_manager = container.state_manager

    @property
    def manifest(self) -> dict:
        """Logic: Returns metadata defining the plugin key, name, and icon"""
        return {"key": "lora", "name": "LoRA", "icon": "🔗"}

    def create_ui(self, parent: Any) -> Any:
        """Logic: Creates and returns the LoraSection UI component, defining a
        callback to update network state"""

        def on_change(
            arg_type: str, name: str, value: Any = None, enabled: bool = True
        ) -> None:
            if hasattr(self.state_manager, "update_network"):
                self.state_manager.update_network(
                    arg_type, name, value, enabled
                )

        return LoraSection(parent, self.lora_manager, on_param_change=on_change)


class EmbeddingPlugin(IPlugin):
    def initialize(self, container: Any) -> None:
        """Logic: Initializes the embedding plugin with necessary managers
        from the container"""
        self.container = container
        self.embedding_manager = container.embeddings
        self.state_manager = container.state_manager

    @property
    def manifest(self) -> dict:
        """Logic: Returns metadata for the Embedding plugin"""
        return {"key": "embedding", "name": "Embedding", "icon": "🧩"}

    def create_ui(self, parent: Any) -> Any:
        """Logic: Instantiates the EmbeddingSection UI, configuring the
        state update callback"""

        def on_change(
            arg_type: str, name: str, value: Any = None, enabled: bool = True
        ) -> None:
            if hasattr(self.state_manager, "update_network"):
                self.state_manager.update_network(
                    arg_type, name, value, enabled
                )

        return EmbeddingSection(
            parent, self.embedding_manager, on_param_change=on_change
        )
