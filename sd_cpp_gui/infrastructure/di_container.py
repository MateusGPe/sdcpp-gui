import threading
from typing import Optional

from sd_cpp_gui.data.db.history_manager import HistoryManager
from sd_cpp_gui.data.db.model_manager import ModelManager
from sd_cpp_gui.data.db.network_manager import EmbeddingManager, LoraManager
from sd_cpp_gui.data.db.queue_manager import QueueManager
from sd_cpp_gui.data.db.settings_manager import SettingsManager
from sd_cpp_gui.data.remote.remote_manager import RemoteManager
from sd_cpp_gui.domain.generation.commands_loader import CommandLoader
from sd_cpp_gui.domain.generation.interfaces import IGenerator
from sd_cpp_gui.domain.generation.processors import ArgumentProcessor
from sd_cpp_gui.domain.generation.states import StateManager
from sd_cpp_gui.domain.generation.types import GenerationState
from sd_cpp_gui.domain.plugins.manager import PluginManager
from sd_cpp_gui.domain.services.autocomplete_service import AutocompleteService
from sd_cpp_gui.infrastructure.paths import AUTOCOMPLETE_FILE, COMMANDS_FILE
from sd_cpp_gui.ui.execution_manager import ExecutionManager


class DependencyContainer:
    """
    Central dependency injection container.
    """

    def __init__(self) -> None:
        """
        Logic: Initializes all singleton managers, services, and
        registers plugins.
        """
        self.settings = SettingsManager()
        self.models = ModelManager()
        self.loras = LoraManager()
        self.embeddings = EmbeddingManager()
        self.history = HistoryManager()
        self.queue = QueueManager()
        self.cmd_loader = CommandLoader(COMMANDS_FILE)
        self.generation_state = GenerationState()
        self.arg_processor = ArgumentProcessor(self.cmd_loader, self.embeddings)
        self.state_manager = StateManager(
            self.cmd_loader, self.generation_state, self.arg_processor
        )
        self.execution_manager: Optional[ExecutionManager] = None
        self.remote = RemoteManager(self.settings)

        self.autocomplete = AutocompleteService(AUTOCOMPLETE_FILE)
        threading.Thread(target=self.autocomplete.load, daemon=True).start()

        self.plugins = PluginManager(self)
        self.plugins.discover_and_register("sd_cpp_gui.plugins")

    def init_execution_manager(
        self, cli_runner: IGenerator, server_runner: IGenerator
    ) -> ExecutionManager:
        """
        Initializes the ExecutionManager using the provided runners.
        Ensures singleton behavior within the container.

        Logic: Lazily initializes ExecutionManager.
        """
        if not self.execution_manager:
            self.execution_manager = ExecutionManager(
                self.settings,
                self.cmd_loader,
                self.models,
                self.embeddings,
                cli_runner,
                server_runner,
            )
        return self.execution_manager
