from __future__ import annotations

import tkinter as tk
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer


class IPlugin(ABC):
    """
    Abstract Interface for application plugins.
    Allows decoupling of new features from the core AppCoordinator.
    """

    @property
    @abstractmethod
    def manifest(self) -> Dict[str, Any]:
        """
        Returns metadata about the plugin.
        Expected keys: 'name', 'version', 'description', 'key'.
        """
        pass

    @abstractmethod
    def initialize(self, container: DependencyContainer) -> None:
        """
        Called when the plugin is registered.
        Use this to retrieve dependencies (Settings, EventBus, etc.)
        and subscribe to events.
        """
        pass

    @abstractmethod
    def create_ui(self, parent: tk.Widget) -> Optional[tk.Widget]:
        """
        Called by the UI Coordinator to generate the plugin's view.
        Returns a Widget to be added to the UI (e.g., in a tab),
        or None if this is a background-only plugin.
        """
        pass
