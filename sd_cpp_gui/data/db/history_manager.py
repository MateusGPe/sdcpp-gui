"""
History Manager
"""

import csv
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, cast

from sd_cpp_gui.data.db.base_manager import ImportExportMixin
from sd_cpp_gui.data.db.database import db
from sd_cpp_gui.data.db.init_db import Database
from sd_cpp_gui.data.db.models import HistoryData, HistoryEntry


class HistoryManager(ImportExportMixin):
    """Manages generation history."""

    def __init__(self) -> None:
        """Logic: Initializes DB."""
        Database()
        self.model_class = HistoryEntry

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def add_entry(
        self,
        model_id: str,
        prompt: str,
        compiled_params: List[Dict[str, Any]],
        output_path: Union[str, List[str]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Adds a new generation entry to the history database.

        Args:
            model_id: The ID of the model used.
            prompt: The positive prompt used.
            compiled_params: List of CLI parameters used for generation.
            output_path: Path or list of paths to the generated files.
            metadata: Optional dictionary of additional metadata (seed,
            time, etc).
        """
        uuid_str = str(uuid.uuid4())
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params_json = json.dumps(compiled_params)
        output_path_str = (
            json.dumps(output_path)
            if isinstance(output_path, list)
            else output_path
        )
        metadata_json = json.dumps(metadata) if metadata else "{}"
        HistoryEntry.create(
            uuid=uuid_str,
            model_id=model_id,
            timestamp=timestamp_str,
            prompt=prompt,
            compiled_params=params_json,
            output_path=output_path_str,
            metadata=metadata_json,
        )

    def get_all(self) -> List[HistoryData]:
        """
        Returns all history entries sorted by timestamp in descending order.

        Returns:
                A list of HistoryData dictionaries.
        """
        query = HistoryEntry.select().order_by(HistoryEntry.timestamp.desc())
        return [self._entry_to_dict(entry) for entry in query]

    def get(self, entry_uuid: str) -> Optional[HistoryData]:
        """
        Retrieves a single history entry by its UUID.

        Args:
                entry_uuid: The unique identifier of the entry.

        Returns:
                The HistoryData dictionary or None if not found.
        """
        entry = HistoryEntry.get_or_none(uuid=entry_uuid)
        return self._entry_to_dict(entry) if entry else None

    def get_page(
        self,
        page: int = 1,
        page_size: int = 20,
        model_id: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[HistoryData]:
        """
        Retrieves a paginated list of history entries with optional filtering.

        Args:
                page: The page number (1-based).
                page_size: Number of items per page.
                model_id: Optional filter by model ID.
                search_query: Optional text search for the prompt.

        Returns:
                A list of HistoryData dictionaries for the requested page.
        """
        query = HistoryEntry.select().order_by(HistoryEntry.timestamp.desc())
        if model_id:
            query = query.where(HistoryEntry.model_id == model_id)
        if search_query:
            query = query.where(HistoryEntry.prompt.contains(search_query))
        query = query.paginate(page, page_size)
        return [self._entry_to_dict(entry) for entry in query]

    def get_count(
        self, model_id: Optional[str] = None, search_query: Optional[str] = None
    ) -> int:
        """
        Returns the total number of history entries matching the filters.

        Args:
                model_id: Optional filter by model ID.
                search_query: Optional text search for the prompt.

        Returns:
                The count of matching entries.
        """
        query = HistoryEntry.select()
        if model_id:
            query = query.where(HistoryEntry.model_id == model_id)
        if search_query:
            query = query.where(HistoryEntry.prompt.contains(search_query))
        return query.count()

    def get_used_model_ids(self) -> List[str]:
        """
        Returns a list of unique model IDs that have been used in the history.

        Returns:
                A list of model ID strings.
        """
        query = HistoryEntry.select(HistoryEntry.model_id).distinct()
        return [str(entry.model_id) for entry in query]

    def _entry_to_dict(self, entry: HistoryEntry) -> HistoryData:
        """Logic: Converts DB entry to TypedDict."""
        out_p = str(entry.output_path).strip()
        if out_p.startswith("[") and out_p.endswith("]"):
            out_p = self._safe_load_json(out_p)
        return HistoryData(
            uuid=str(entry.uuid),
            model_id=str(entry.model_id),
            timestamp=str(entry.timestamp),
            prompt=str(entry.prompt),
            compiled_params=self._safe_load_json(entry.compiled_params, []),
            output_path=out_p,
            metadata=self._safe_load_json(entry.metadata, {}),
        )

    def export_to_toml(self, filepath: str, root_key: str = "history") -> None:
        """
        Exports the entire history to a TOML file.

        Args:
                filepath: Destination path.
                root_key: Root key in the TOML file.
        """
        super().export_to_toml(filepath, root_key=root_key)

    def import_from_toml(
        self, filepath: str, root_key: str = "history"
    ) -> None:
        """
        Imports history entries from a TOML file.

        Args:
                filepath: Source path.
                root_key: Root key to look for.
        """
        super().import_from_toml(filepath, root_key=root_key)

    def _process_import_data(
        self, data: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """
        Internal method to process and bulk insert history data.

        Args:
                data: List of history entry dictionaries.
        """
        if not isinstance(data, list):
            return
        with db.atomic():
            for item in data:
                out_path = item.get("output_path")
                if isinstance(out_path, list):
                    out_path = json.dumps(out_path)
                HistoryEntry.replace(
                    uuid=item.get("uuid", str(uuid.uuid4())),
                    model_id=item.get("model_id"),
                    timestamp=item.get("timestamp"),
                    prompt=item.get("prompt", ""),
                    compiled_params=json.dumps(item.get("compiled_params", [])),
                    output_path=out_path,
                    metadata=json.dumps(item.get("metadata", {})),
                ).execute()

    def export_to_csv(self, filepath: str) -> None:
        """
        Exports the history to a CSV file for spreadsheet use.

        Args:
                filepath: Destination CSV path.
        """
        data = self.get_all()
        if not data:
            return
        fieldnames = [
            "uuid",
            "model_id",
            "timestamp",
            "prompt",
            "compiled_params",
            "output_path",
            "metadata",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                row_copy = cast(Dict[str, Any], row.copy())
                row_copy["compiled_params"] = json.dumps(
                    row["compiled_params"], ensure_ascii=False
                )
                row_copy["metadata"] = json.dumps(
                    row["metadata"], ensure_ascii=False
                )
                if isinstance(row["output_path"], list):
                    row_copy["output_path"] = json.dumps(
                        row["output_path"], ensure_ascii=False
                    )
                writer.writerow(row_copy)

    def import_from_csv(self, filepath: str) -> None:
        """
        Imports history entries from a CSV file.

        Args:
                filepath: Source CSV path.
        """
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            with db.atomic():
                for row in reader:
                    HistoryEntry.replace(
                        uuid=row["uuid"],
                        model_id=row["model_id"],
                        timestamp=row["timestamp"],
                        prompt=row["prompt"],
                        compiled_params=row["compiled_params"],
                        output_path=row["output_path"],
                        metadata=row["metadata"],
                    ).execute()
