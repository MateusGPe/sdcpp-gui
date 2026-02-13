"""
Network Manager (LoRA/Embedding)
"""

import glob
import json
import os
import unicodedata
import uuid
from typing import Any, Dict, List, Optional, Set, Type, Union

from peewee import fn

from sd_cpp_gui.data.db.base_manager import ImportExportMixin
from sd_cpp_gui.data.db.database import db
from sd_cpp_gui.data.db.init_db import Database
from sd_cpp_gui.data.db.models import (
    BaseModel,
    EmbeddingEntry,
    LoraEntry,
    NetworkData,
)
from sd_cpp_gui.data.remote.types import RemoteVersionDTO
from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)


class _NetworkManagerBase(ImportExportMixin):
    """Base class for managing networks (LoRA/Embedding)."""

    def __init__(self, model_class: Type[BaseModel]) -> None:
        """Logic: Initializes base manager."""
        Database()
        self.model_class = model_class

    def _normalize(self, text: str) -> str:
        """Standardize unicode text to NFC form.

        Logic: Normalizes unicode string."""
        if not text:
            return ""
        return unicodedata.normalize("NFC", text)

    def scan_and_import_folder(self, folder_path: str) -> int:
        """
        Scans a directory for model files and imports any that aren't in the DB.

        Args:
                folder_path: Path to the directory to scan.

        Returns:
                The number of new files added.
        """
        result = self.sync_folder(folder_path)
        return result["added"]

    def _try_load_sidecar_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Attempts to load metadata from adjacent JSON files.

        CRITICAL FOR METADATA CORRECTNESS:
        Even though the 'file_path' might be sanitized
        (e.g., 'blue_archive_lora.safetensors'),
        we look for the corresponding 'blue_archive_lora.json'.
        Inside that JSON, we read the ORIGINAL Model/Version
        names (e.g., 'Blue Archive [Anime Style]').
        This ensures the UI displays the correct, pretty name
        (Alias) even if the
        filesystem uses a sanitized, portable name.

        Logic: Tries to read metadata from .json/.civitai.info sidecar files.
        """
        base_path = os.path.splitext(file_path)[0]
        version_file = f"{base_path}.json"
        parent_file = f"{base_path}.model.json"
        auto1111_file = f"{base_path}.civitai.info"
        meta: Dict[str, Any] = {}
        version_data = {}
        model_data = {}
        if os.path.exists(version_file):
            try:
                with open(version_file, "r", encoding="utf-8") as f:
                    version_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                logger.warning(f"Failed to read sidecar JSON: {version_file}")
        if os.path.exists(parent_file):
            try:
                with open(parent_file, "r", encoding="utf-8") as f:
                    model_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        if version_data:
            if "id" in version_data and "modelId" in version_data:
                meta["remote_source"] = "civitai"
                meta["remote_id"] = str(version_data.get("modelId"))
                meta["remote_version_id"] = str(version_data.get("id"))
                meta["base_model"] = version_data.get("baseModel")
                meta["description"] = version_data.get("description")
                if "trainedWords" in version_data:
                    meta["trigger_words"] = ", ".join(
                        version_data["trainedWords"]
                    )
                v_name = version_data.get("name", "").strip()
                m_name = model_data.get("name", "").strip()
                if m_name and v_name:
                    if m_name in v_name:
                        meta["alias"] = v_name
                    else:
                        meta["alias"] = f"{m_name} ({v_name})"
                elif m_name:
                    meta["alias"] = m_name
                elif v_name:
                    meta["alias"] = v_name
                return meta
        if os.path.exists(auto1111_file):
            try:
                with open(auto1111_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta["remote_source"] = "civitai"
                meta["remote_id"] = str(data.get("modelId"))
                meta["remote_version_id"] = str(data.get("id"))
                meta["base_model"] = data.get("baseModel")
                meta["description"] = data.get("description")
                if "trainedWords" in data:
                    meta["trigger_words"] = ", ".join(data["trainedWords"])
                m_name = data.get("model", {}).get("name", "")
                v_name = data.get("name", "")
                if m_name and v_name:
                    if m_name in v_name:
                        meta["alias"] = v_name
                    else:
                        meta["alias"] = f"{m_name} ({v_name})"
                elif v_name:
                    meta["alias"] = v_name
                return meta
            except (json.JSONDecodeError, OSError):
                pass
        if version_data and "remote_version_id" in version_data:
            meta.update(
                {
                    k: v
                    for k, v in version_data.items()
                    if k
                    in [
                        "remote_source",
                        "remote_id",
                        "remote_version_id",
                        "base_model",
                        "description",
                        "content_hash",
                        "alias",
                        "trigger_words",
                    ]
                }
            )
        return meta

    def sync_folder(self, folder_path: str) -> Dict[str, int]:
        """
        Synchronizes the database with the physical files in a folder.
        1. Adds new files found on disk.
        2. Removes database entries for files that no longer exist.

        Args:
                folder_path: Path to the directory.

        Returns:
                A dictionary with 'added' and 'removed' counts.
        """
        if not os.path.exists(folder_path):
            return {"added": 0, "removed": 0}
        extensions = ["*.bin", "*.gguf", "*.safetensors", "*.pt"]
        found_files: List[str] = []
        for ext in extensions:
            found_files.extend(
                glob.glob(os.path.join(folder_path, "**", ext), recursive=True)
            )
        physical_map = {
            os.path.normcase(os.path.abspath(p)): os.path.abspath(p)
            for p in found_files
        }
        stats = {"added": 0, "removed": 0}
        with db.atomic():
            abs_folder = os.path.abspath(folder_path)
            norm_abs_folder = os.path.normcase(abs_folder)
            all_db_entries = self.model_class.select()
            db_entries_map = {}
            for entry in all_db_entries:
                entry_path = str(entry.path)
                if os.path.normcase(entry_path).startswith(norm_abs_folder):
                    db_entries_map[
                        os.path.normcase(os.path.abspath(entry_path))
                    ] = entry
            for norm_db_path, entry in db_entries_map.items():
                if norm_db_path not in physical_map:
                    entry.delete_instance()
                    stats["removed"] += 1
            for norm_phys_path, original_abs_path in physical_map.items():
                if norm_phys_path not in db_entries_map:
                    filename = os.path.basename(original_abs_path)
                    name_no_ext = self._normalize(os.path.splitext(filename)[0])
                    restored_meta = self._try_load_sidecar_metadata(
                        original_abs_path
                    )
                    final_alias = restored_meta.get("alias")
                    if not final_alias:
                        final_alias = name_no_ext
                    final_alias = self._normalize(final_alias)
                    self.model_class.create(
                        id=str(uuid.uuid4()),
                        path=original_abs_path,
                        dir_path=os.path.dirname(original_abs_path),
                        filename=filename,
                        name=name_no_ext,
                        alias=final_alias,
                        trigger_words=restored_meta.get("trigger_words", ""),
                        remote_source=restored_meta.get("remote_source"),
                        remote_id=restored_meta.get("remote_id"),
                        remote_version_id=restored_meta.get(
                            "remote_version_id"
                        ),
                        base_model=restored_meta.get("base_model"),
                        description=restored_meta.get("description"),
                        content_hash=restored_meta.get("content_hash"),
                    )
                    stats["added"] += 1
        return stats

    def register_from_remote(
        self,
        file_path: str,
        metadata: RemoteVersionDTO,
        hash_value: Optional[str] = None,
    ) -> None:
        """Registers a file using rich metadata from remote.

        Logic: Registers or updates local file record with remote metadata."""
        file_path = os.path.abspath(file_path)
        folder_path = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name_no_ext = self._normalize(os.path.splitext(filename)[0])
        triggers = ", ".join(metadata.get("trigger_words", []))
        desc = metadata.get("description", "")
        if desc and len(desc) > 500:
            desc = desc[:497] + "..."
        with db.atomic():
            existing = self.model_class.get_or_none(
                (self.model_class.path == file_path)  # type: ignore
                | (self.model_class.remote_version_id == str(metadata["id"]))  # type: ignore
            )
            alias_name = self._normalize(metadata["name"])
            record_data = {
                "path": file_path,
                "dir_path": folder_path,
                "filename": filename,
                "alias": alias_name,
                "name": name_no_ext,
                "trigger_words": triggers,
                "preferred_strength": 1.0,
                "remote_source": "civitai",
                "remote_id": str(metadata["model_id"]),
                "remote_version_id": str(metadata["id"]),
                "base_model": metadata.get("base_model", "Unknown"),
                "description": desc,
            }
            if hash_value:
                record_data["content_hash"] = hash_value
            if existing:
                self.model_class.update(**record_data).where(
                    self.model_class.id == existing.id  # type: ignore
                ).execute()
            else:
                record_data["id"] = str(uuid.uuid4())
                self.model_class.create(**record_data)

    def update_hash(self, path: str, hash_value: str) -> None:
        """Updates just the hash for a specific file path.

        Logic: Updates hash field for file."""
        self.model_class.update(content_hash=hash_value).where(
            self.model_class.path == os.path.abspath(path)  # type: ignore
        ).execute()

    def find_best_match(
        self,
        hash_val: Optional[str],
        remote_id: Optional[str],
        filename: Optional[str],
    ) -> Optional[NetworkData]:
        """
        Smart lookup strategy:
        1. Exact Hash Match
        2. Remote Version ID Match
        3. Exact Filename/Alias Match

        Logic: Finds DB entry by hash, remote ID, or filename fuzzy match.
        """
        if hash_val:
            entry = (
                self.model_class.select()
                .where(self.model_class.content_hash == hash_val)  # type: ignore
                .first()
            )
            if entry:
                return self._entry_to_dict(entry)
        if remote_id:
            entry = (
                self.model_class.select()
                .where(self.model_class.remote_version_id == remote_id)  # type: ignore
                .first()
            )
            if entry:
                return self._entry_to_dict(entry)
        if filename:
            normalized = self._normalize(filename)
            candidates: Set[str] = {normalized}
            candidates.add(normalized.replace(" ", "_"))
            candidates.add(normalized.replace("_", " "))
            entry = (
                self.model_class.select()
                .where(
                    (self.model_class.name.in_(candidates))  # type: ignore
                    | (self.model_class.alias.in_(candidates))  # type: ignore
                )
                .first()
            )
            if entry:
                return self._entry_to_dict(entry)
            norm_lower = normalized.lower()
            entry = (
                self.model_class.select()
                .where(
                    (fn.Lower(self.model_class.name) == norm_lower)  # type: ignore
                    | (fn.Lower(self.model_class.alias) == norm_lower)  # type: ignore
                )
                .first()
            )
            if entry:
                return self._entry_to_dict(entry)
        return None

    def update_metadata(
        self,
        item_id: str,
        alias: str,
        strength: float,
        triggers: str,
        base_model: Optional[str] = None,
    ) -> None:
        """
        Manually updates the metadata for a network item.

        Args:
                item_id: The database ID of the item.
                alias: The display name/alias.
                strength: The preferred default strength.
                triggers: Comma-separated trigger words.
                base_model: Optional base model architecture.
        """
        update_dict = {
            "alias": self._normalize(alias),
            "preferred_strength": strength,
            "trigger_words": triggers,
        }
        if base_model is not None:
            update_dict["base_model"] = base_model
        self.model_class.update(**update_dict).where(
            self.model_class.id == item_id  # type: ignore
        ).execute()

    def get_known_folders(self) -> List[str]:
        """Returns a list of known folders.

        Logic: Returns list of directories tracked in DB."""
        query = self.model_class.select(self.model_class.dir_path).distinct()  # type: ignore
        return [entry.dir_path for entry in query if entry.dir_path]

    def get_by_folder(self, folder_path: str) -> List[NetworkData]:
        """Returns items from a specific folder.

        Logic: Returns items in specific folder."""
        query = (
            self.model_class.select()
            .where(self.model_class.dir_path == folder_path)  # type: ignore
            .order_by(self.model_class.alias.asc())  # type: ignore
        )
        return [self._entry_to_dict(e) for e in query]

    def get_all(self) -> List[NetworkData]:
        """Returns all items.

        Logic: Returns all items."""
        query = self.model_class.select().order_by(self.model_class.alias.asc())  # type: ignore
        return [self._entry_to_dict(e) for e in query]

    def get_remote_index(self) -> Dict[str, str]:
        """
        Returns a map of {remote_version_id: local_path} for fast lookup.
        Used by the browser to check ownership.

        Logic: Returns mapping of remote IDs to local paths.
        """
        query = self.model_class.select(
            self.model_class.remote_version_id,
            self.model_class.path,  # type: ignore
        )
        return {
            str(e.remote_version_id): str(e.path)
            for e in query
            if e.remote_version_id
        }

    def delete_item(self, item_id: str) -> None:
        """Logic: Deletes DB entry."""
        self.model_class.delete().where(
            self.model_class.id == item_id  # type: ignore
        ).execute()

    def _entry_to_dict(self, entry: Any) -> NetworkData:
        """Logic: Converts DB model to TypedDict."""
        return NetworkData(
            alias=str(entry.alias) if entry.alias else str(entry.name),
            dir_path=str(entry.dir_path),
            filename=str(entry.filename),
            id=str(entry.id),
            name=str(entry.name),
            path=str(entry.path),
            preferred_strength=float(entry.preferred_strength),
            trigger_words=str(entry.trigger_words)
            if entry.trigger_words
            else "",
            remote_id=str(entry.remote_id) if entry.remote_id else None,
            remote_version_id=str(entry.remote_version_id)
            if entry.remote_version_id
            else None,
            base_model=str(entry.base_model) if entry.base_model else None,
            description=str(entry.description) if entry.description else None,
            remote_source=str(entry.remote_source)
            if entry.remote_source
            else None,
            content_hash=str(entry.content_hash)
            if entry.content_hash
            else None,
        )

    def export_to_toml(self, filepath: str, root_key: str = "data") -> None:
        """Exports all items to a TOML file.

        Logic: Exports to TOML."""
        key = f"{self.model_class.__name__.lower()}s"
        super().export_to_toml(filepath, root_key=key)

    def import_from_toml(self, filepath: str, root_key: str = "data") -> None:
        """Imports items from a TOML file.

        Logic: Imports from TOML."""
        key = f"{self.model_class.__name__.lower()}s"
        super().import_from_toml(filepath, root_key=key)

    def _process_import_data(
        self, data: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Processes and inserts imported network data.

        Logic: Bulk inserts/updates imported data."""
        if not isinstance(data, list):
            return
        with db.atomic():
            for item in data:
                if "path" in item and os.path.exists(item["path"]):
                    self.model_class.replace(  # type: ignore
                        id=item.get("id", str(uuid.uuid4())),
                        path=item["path"],
                        dir_path=item.get("dir_path", ""),
                        filename=item.get("filename", ""),
                        alias=self._normalize(item.get("alias", "")),
                        trigger_words=item.get("trigger_words", ""),
                        preferred_strength=item.get("preferred_strength", 1.0),
                        name=self._normalize(item.get("name", "")),
                        remote_source=item.get("remote_source"),
                        remote_id=item.get("remote_id"),
                        remote_version_id=item.get("remote_version_id"),
                        base_model=item.get("base_model"),
                        description=item.get("description"),
                        content_hash=item.get("content_hash"),
                    ).execute()


class LoraManager(_NetworkManagerBase):
    """CRUD for LoRAs."""

    def __init__(self) -> None:
        """Logic: Initializes with LoraEntry."""
        super().__init__(LoraEntry)

    def update_lora_metadata(self, *args: Any, **kwargs: Any) -> None:
        """Alias for update_metadata.

        Logic: Alias for update_metadata."""
        return self.update_metadata(*args, **kwargs)

    def delete_lora(self, *args: Any, **kwargs: Any) -> None:
        """Alias for delete_item.

        Logic: Alias for delete_item."""
        return self.delete_item(*args, **kwargs)


class EmbeddingManager(_NetworkManagerBase):
    """CRUD for Embeddings."""

    def __init__(self) -> None:
        """Logic: Initializes with EmbeddingEntry."""
        super().__init__(EmbeddingEntry)
