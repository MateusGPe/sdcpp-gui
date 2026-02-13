"""
Remote Manager Factory.
"""

from __future__ import annotations

import os
import threading
from typing import Dict, Optional

from sd_cpp_gui.data.db.settings_manager import SettingsManager
from sd_cpp_gui.data.remote.civitai_adapter import CivitaiAdapter
from sd_cpp_gui.data.remote.downloader import DownloadManager
from sd_cpp_gui.data.remote.hf_adapter import HuggingFaceAdapter
from sd_cpp_gui.data.remote.remote import IRemoteRepository
from sd_cpp_gui.data.remote.types import RemoteModelDTO, RemoteVersionDTO
from sd_cpp_gui.domain.services.sidecar_service import SidecarService
from sd_cpp_gui.domain.utils.sanitization import make_filename_portable
from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)


class RemoteManager:
    """
    Factory that manages remote repository connections and downloads.
    """

    def __init__(self, settings_manager: SettingsManager) -> None:
        """
        Logic: Initializes remote manager with settings, downloader,
        and sidecar service.
        """
        self.settings = settings_manager
        self._cache: Dict[str, IRemoteRepository] = {}
        self.downloader = DownloadManager()
        self.sidecar = SidecarService(settings_manager)

    def get_repository(self, provider: str = "civitai") -> IRemoteRepository:
        """
        Returns the requested repository adapter, creating it if necessary.
        Args:
            provider: The key of the provider ('civitai', 'huggingface').

        Logic: Returns singleton instance of requested repository adapter
        (Civitai/HF).
        """
        provider = provider.lower()
        if provider in self._cache:
            return self._cache[provider]
        if provider == "civitai":
            self._cache["civitai"] = CivitaiAdapter(
                api_token=self.settings.get_str("civitai_api_key", "") or None
            )
        elif provider == "huggingface":
            self._cache["huggingface"] = HuggingFaceAdapter(
                api_token=self.settings.get_str("hf_api_token", "") or None
            )
        else:
            return self.get_repository("civitai")
        return self._cache[provider]

    def fetch_rich_metadata(
        self, hash_value: str = "", version_id: str = ""
    ) -> Optional[RemoteVersionDTO]:
        """
        Orchestrates fetching version data AND parent model data to ensure
        fields like 'base_model' and 'type' are populated.

        Logic: Fetches version details via hash or ID, and enriches with
        parent model data.
        """
        repo = self.get_repository("civitai")
        version_dto: Optional[RemoteVersionDTO] = None
        if hash_value:
            version_dto = repo.get_version_by_hash(hash_value)
        elif version_id:
            version_dto = repo.get_version_details(version_id)
        if not version_dto:
            return None
        try:
            parent: Optional[RemoteModelDTO] = repo.get_model_details(
                version_dto["model_id"]
            )
            if parent:
                if "type" not in version_dto:
                    version_dto["type"] = parent["type"]  # type: ignore
                v_name = version_dto["name"]
                p_name = parent["name"]
                if p_name and p_name not in v_name:
                    version_dto["name"] = f"{p_name} ({v_name})"
                version_dto["_parent_model"] = parent  # type: ignore
        except Exception as e:
            logger.warning(f"Could not fetch parent model details: {e}")
        return version_dto

    def download_with_metadata(
        self,
        url: str,
        dest_folder: str,
        filename: str,
        metadata: RemoteVersionDTO,
        preview_url: Optional[str],
    ) -> None:
        """
        Starts a download and saves metadata/preview sidecars.
        CRITICAL: This method enforces filename sanitization.
        Even if the UI passed a sanitized string, we double-check here
        to ensure the sidecar JSON and the image file share the exact
        same safe basename.
        Args:
            url: The download URL.
            dest_folder: Directory to save files.
            filename: Target filename.
            metadata: The DTO containing model info (Saved AS IS).
            preview_url: Optional URL for a preview image.

        Logic: Sanitizes filename, starts async download, and saves
        metadata/preview sidecars.
        """
        safe_filename = make_filename_portable(filename)
        headers = {}
        civitai_key = self.settings.get_str("civitai_api_key", "")
        if civitai_key and "civitai.com" in url:
            headers["Authorization"] = f"Bearer {civitai_key}"
        self.downloader.start_download(
            url,
            dest_folder,
            safe_filename,
            callback=lambda path: self._on_download_complete(path, metadata),
            headers=headers,
        )
        full_path = os.path.join(dest_folder, safe_filename)
        self.sidecar.save_metadata(full_path, metadata)
        if preview_url:
            threading.Thread(
                target=self.sidecar.download_preview,
                args=(full_path, preview_url),
                daemon=True,
            ).start()

    def _on_download_complete(
        self, file_path: str, metadata: RemoteVersionDTO
    ) -> None:
        """
        Callback fired when the main file finishes downloading.
        Triggers a database import event.

        Logic: Publishes event on download completion.
        """
        from sd_cpp_gui.infrastructure.event_bus import EventBus

        EventBus.publish(
            "remote_download_complete",
            {"path": file_path, "metadata": metadata},
        )

    def clear_cache(self) -> None:
        """Forces re-initialization of adapters (useful if settings change).

        Logic: Clears adapter cache."""
        self._cache.clear()
