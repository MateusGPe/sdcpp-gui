from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, cast

if TYPE_CHECKING:
    from sd_cpp_gui.data.db.data_manager import (
        EmbeddingManager,
        LoraManager,
        ModelManager,
    )


class OwnershipChecker:
    """Helper to check if a remote item exists locally."""

    def __init__(
        self, models: ModelManager, loras: LoraManager, embeds: EmbeddingManager
    ) -> None:
        """Logic: Initializes managers and builds initial index."""
        self.managers = {
            "Checkpoint": models,
            "LoRA": loras,
            "Embedding": embeds,
        }
        self.indices: Dict[str, Any] = {}
        self.refresh()

    def refresh(self) -> None:
        """Rebuilds the ownership index.

        Logic: Fetches remote indices from all managers and aggregates them."""
        for key, mgr in self.managers.items():
            self.indices[key] = cast(Any, mgr).get_remote_index()

    def check_version(self, model_type: str, version_id: str) -> bool:
        """Returns True if the specific version is installed.

        Logic: Checks if version_id exists in the cached index
        for the given type."""
        if model_type not in self.indices:
            return False
        return str(version_id) in self.indices[model_type]
