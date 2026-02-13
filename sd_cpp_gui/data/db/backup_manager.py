"""
Backup Manager
"""

import json
from typing import Any, Dict, List, Union

from sd_cpp_gui.data.db.base_manager import ImportExportMixin
from sd_cpp_gui.data.db.database import db
from sd_cpp_gui.data.db.history_manager import HistoryManager
from sd_cpp_gui.data.db.model_manager import ModelManager
from sd_cpp_gui.data.db.models import QueueEntry, SettingModel
from sd_cpp_gui.data.db.network_manager import EmbeddingManager, LoraManager
from sd_cpp_gui.data.db.queue_manager import QueueManager


class BackupManager(ImportExportMixin):
    """Manages full database Backup/Restore."""

    def __init__(self) -> None:
        """Logic: Initializes all managers."""
        self.history = HistoryManager()
        self.models = ModelManager()
        self.loras = LoraManager()
        self.embeddings = EmbeddingManager()
        self.queue = QueueManager()

    def get_all(self) -> Dict[str, Any]:
        """Returns all data from the database.

        Returns:
            A dictionary containing 'settings', 'models', 'loras', 'embeddings',
            'history', and 'queue' data.
        """
        settings_data = {s.key: s.value for s in SettingModel.select()}
        return {
            "settings": settings_data,
            "models": self.models.get_all(),
            "loras": self.loras.get_all(),
            "embeddings": self.embeddings.get_all(),
            "history": self.history.get_all(),
            "queue": self.queue.get_all(),
        }

    def export_to_toml(self, filepath: str, root_key: str = "backup") -> None:
        """
        Exports all database data to a TOML file.

        Args:
                filepath: The destination path for the TOML file.
                root_key: The root key in the TOML file (defaults to 'backup').
        """
        super().export_to_toml(filepath, root_key=root_key)

    def import_from_toml(self, filepath: str, root_key: str = "backup") -> None:
        """
        Imports all data from a TOML file into the database.

        Args:
                filepath: The path to the TOML file.
                root_key: The root key to look for in the TOML file.
        """
        super().import_from_toml(filepath, root_key=root_key)

    def _process_import_data(
        self, data: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """
        Internal method to process and restore data from a dictionary.

        Args:
                data: A dictionary containing the backup data structure.
        """
        if not isinstance(data, dict):
            return
        if "settings" in data and isinstance(data["settings"], dict):
            with db.atomic():
                for key, value in data["settings"].items():
                    SettingModel.replace(key=key, value=value).execute()
        if "models" in data:
            self.models._process_import_data(data["models"])
        if "loras" in data:
            self.loras._process_import_data(data["loras"])
        if "embeddings" in data:
            self.embeddings._process_import_data(data["embeddings"])
        if "history" in data:
            self.history._process_import_data(data["history"])
        if "queue" in data:
            self._import_queue(data["queue"])

    def _import_queue(self, queue_data: List[Dict[str, Any]]) -> None:
        """
        Internal method to import queue items while preserving their UUIDs.

        Args:
                queue_data: A list of dictionaries representing queue entries.
        """
        with db.atomic():
            for item in queue_data:
                c_params = item.get("compiled_params", [])
                if isinstance(c_params, (list, dict)):
                    c_params = json.dumps(c_params)
                meta = item.get("metadata", {})
                if isinstance(meta, (list, dict)):
                    meta = json.dumps(meta)
                QueueEntry.replace(
                    uuid=item["uuid"],
                    model_id=item["model_id"],
                    timestamp=item["timestamp"],
                    prompt=item["prompt"],
                    compiled_params=c_params,
                    metadata=meta,
                    status=item.get("status", "pending"),
                    priority=item.get("priority", 0),
                ).execute()
