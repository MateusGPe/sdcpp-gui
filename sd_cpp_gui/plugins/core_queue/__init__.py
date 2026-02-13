from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Optional

from sd_cpp_gui.constants import MSG_MODEL_SELECTED
from sd_cpp_gui.domain.plugins.interface import IPlugin
from sd_cpp_gui.infrastructure.event_bus import EventBus
from sd_cpp_gui.plugins.core_queue.panel import QueuePanel

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer


class QueuePlugin(IPlugin):
    def __init__(self) -> None:
        """Logic: Initializes plugin."""
        self.container: Optional[DependencyContainer] = None

    @property
    def manifest(self) -> Dict[str, Any]:
        """Logic: Returns manifest."""
        return {
            "name": "Queue",
            "key": "queue",
            "icon": "🕒",
            "description": "Manages the generation queue.",
        }

    def initialize(self, container: DependencyContainer) -> None:
        """Logic: Injects container."""
        self.container = container

    def create_ui(self, parent: tk.Widget) -> Optional[tk.Widget]:
        """Logic: Creates UI."""
        if not self.container:
            return None
        em = self.container.execution_manager
        mm = self.container.models

        def load_params(prompt: str, item_data: Dict[str, Any]) -> None:
            model_id = item_data.get("model_id", "")
            if model_id:
                EventBus.publish(MSG_MODEL_SELECTED, model_id)
            restored = self.container.arg_processor.restore_from_args(
                model_id=model_id,
                prompt=prompt,
                compiled_params=item_data.get("compiled_params", []),
            )
            self.container.state_manager.restore_state(restored)

        return QueuePanel(parent, em, mm, load_params)
