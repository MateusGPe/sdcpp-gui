from sd_cpp_gui.ui.app import logic_handlers
from sd_cpp_gui.ui.features.history.history_window import HistoryWindow


class HistoryPresenter:
    def __init__(self, coordinator, history_manager, model_manager, cmd_loader):
        """Logic: Stores references to coordinator and managers."""
        self.coordinator = coordinator
        self.history = history_manager
        self.models = model_manager
        self.cmd_loader = cmd_loader

    def open_window(self, parent_window):
        """Logic: Opens the HistoryWindow instance."""
        HistoryWindow(
            parent_window,
            self.history,
            self.models,
            self.cmd_loader,
            self._on_load_session,
        )

    def _on_load_session(self, uuid: str) -> None:
        """Logic: Restores session data via logic handlers, updates UI
        parameters, and shows preview image."""
        data = logic_handlers.restore_session_data(
            uuid,
            self.history,
            self.coordinator.arg_processor,
            self.coordinator.state_manager,
        )
        if data:
            self.coordinator.load_parameters(
                self.history.get(uuid).get("prompt", ""),
                {
                    "model_id": data["model_id"],
                    "compiled_params": self.history.get(uuid).get(
                        "compiled_params", []
                    ),
                },
            )
            if data["image_path"]:
                self.coordinator.show_preview_image(data["image_path"])
