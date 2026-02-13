"""
Adapter for Civitai Repository.
"""

from typing import Any, Dict, List, Optional

from sd_cpp_gui.data.remote.civitai_client import CivitaiClient, ModelType
from sd_cpp_gui.data.remote.remote import IRemoteRepository
from sd_cpp_gui.data.remote.types import (
    RemoteFileDTO,
    RemoteImageDTO,
    RemoteModelDTO,
    RemoteVersionDTO,
    RemoteVersionSummary,
)
from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)


class CivitaiAdapter(IRemoteRepository):
    """
    Implementation of IRemoteRepository for Civitai.
    Adapts raw JSON responses from the CivitaiClient to standardized DTOs.
    """

    def __init__(self, api_token: Optional[str] = None) -> None:
        """Logic: Initializes the Civitai client with an optional API token"""
        self.client = CivitaiClient(api_token)

    def _map_to_dto(self, raw: Dict[str, Any]) -> RemoteModelDTO:
        """
        Maps raw API JSON to our standardized DTO.

        Logic: Converts raw API JSON data into a standardized RemoteModelDTO
        dictionary, handling optional fields and nested structures like model
        versions and stats
        """
        image_url: Optional[str] = None
        versions_summary: List[RemoteVersionSummary] = []
        base_model: Optional[str] = None
        model_versions = raw.get("modelVersions")
        if model_versions and isinstance(model_versions, list):
            for v in model_versions:
                versions_summary.append(
                    {
                        "id": str(v.get("id", "")),
                        "name": v.get("name", "Unknown"),
                        "base_model": v.get("baseModel"),
                        "published_at": v.get("publishedAt"),
                    }
                )
            if len(model_versions) > 0:
                mv = model_versions[0]
                if not base_model:
                    base_model = mv.get("baseModel")
                images = mv.get("images")
                if images and isinstance(images, list) and (len(images) > 0):
                    image_url = images[0].get("url")
        stats = raw.get("stats", {})
        return {
            "id": str(raw.get("id", "")),
            "name": raw.get("name", "Unknown"),
            "creator": raw.get("creator", {}).get("username", "Unknown"),
            "image_url": image_url,
            "type": raw.get("type", "Checkpoint"),
            "nsfw": raw.get("nsfw", False),
            "tags": raw.get("tags", []),
            "download_count": int(stats.get("downloadCount", 0)),
            "rating": float(stats.get("rating", 0.0)),
            "base_model": base_model,
            "description": raw.get("description", ""),
            "versions": versions_summary,
        }

    def _map_version_to_dto(self, raw: Dict[str, Any]) -> RemoteVersionDTO:
        """Maps raw version JSON to RemoteVersionDTO.

        Logic: Transforms raw version JSON into a RemoteVersionDTO,
        extracting file details, primary download URLs, and image metadata
        """
        files: List[RemoteFileDTO] = []
        primary_download_url = ""
        for f in raw.get("files", []):
            is_primary = f.get("primary", False)
            dl_url = f.get("downloadUrl", "")
            if is_primary:
                primary_download_url = dl_url
            files.append(
                {
                    "id": str(f.get("id", "")),
                    "name": f.get("name", "unknown"),
                    "size_kb": f.get("sizeKb", 0),
                    "download_url": dl_url,
                    "primary": is_primary,
                    "pickle_scan_result": f.get("pickleScanResult"),
                    "virus_scan_result": f.get("virusScanResult"),
                    "hashes": f.get("hashes", {}),
                }
            )
        if not primary_download_url and files:
            primary_download_url = files[0]["download_url"]
        images: List[RemoteImageDTO] = []
        for img in raw.get("images", []):
            if "url" in img:
                images.append(
                    {
                        "url": img["url"],
                        "nsfw": img.get("nsfw", "None") != "None",
                        "width": img.get("width", 0),
                        "height": img.get("height", 0),
                        "meta": img.get("meta"),
                    }
                )
        return {
            "id": str(raw.get("id", "")),
            "model_id": str(raw.get("modelId", "")),
            "name": raw.get("name", "Unknown"),
            "description": raw.get("description", ""),
            "base_model": raw.get("baseModel", "Unknown"),
            "published_at": raw.get("publishedAt", ""),
            "trigger_words": raw.get("trainedWords", []),
            "files": files,
            "images": images,
            "download_url": primary_download_url,
            "stats": raw.get("stats", {}),
        }

    def search_models(
        self,
        query: str,
        model_type: Optional[str] = None,
        base_model: Optional[str] = None,
        page: int = 1,
        nsfw: bool = False,
    ) -> List[RemoteModelDTO]:
        """
        Searches for models on Civitai using various filters.

        Args:
                query: Search keywords.
                model_type: Filter by type ('LoRA', 'Checkpoint', etc).
                base_model: Filter by base architecture (e.g., 'SDXL 1.0').
                page: Pagination index.
                nsfw: Whether to include NSFW content.

        Returns:
                A list of standardized RemoteModelDTOs.
        """
        c_type: Optional[ModelType] = None
        type_map = {
            "LoRA": ModelType.LORA,
            "Checkpoint": ModelType.CHECKPOINT,
            "Embedding": ModelType.TEXTUAL_INVERSION,
            "ControlNet": ModelType.CONTROLNET,
            "Hypernetwork": ModelType.HYPERNETWORK,
        }
        if model_type in type_map:
            c_type = type_map[model_type]
        if base_model and base_model.lower() == "all":
            base_model = None
        try:
            response = self.client.get_models(
                query=query,
                page=page,
                types=c_type,
                nsfw=nsfw,
                base_model=base_model,
            )
            items = response.get("items", [])
            return [self._map_to_dto(item) for item in items]
        except Exception as e:
            logger.error(f"Civitai search error: {e}")
            return []

    def get_model_details(self, model_id: str) -> Optional[RemoteModelDTO]:
        """
        Retrieves comprehensive metadata for a specific model.

        Args:
                model_id: The unique identifier on Civitai.

        Returns:
                A RemoteModelDTO or None if not found.
        """
        try:
            if not model_id.isdigit():
                return None
            raw = self.client.get_model(int(model_id))
            return self._map_to_dto(raw)  # type: ignore
        except Exception:
            return None

    def get_version_details(
        self, version_id: str
    ) -> Optional[RemoteVersionDTO]:
        """
        Retrieves details for a specific version of a model (files, triggers).

        Args:
                version_id: The unique version identifier.

        Returns:
                A RemoteVersionDTO or None if not found.
        """
        try:
            if not version_id.isdigit():
                return None
            raw = self.client.get_model_version(int(version_id))
            return self._map_version_to_dto(raw)  # type: ignore
        except Exception:
            return None

    def get_version_by_hash(self, file_hash: str) -> Optional[RemoteVersionDTO]:
        """Fetches version details via file hash.

        Logic: Looks up a model version by its file hash and returns
        the mapped DTO
        """
        try:
            raw = self.client.get_model_version_by_hash(file_hash)
            return self._map_version_to_dto(raw)  # type: ignore
        except Exception:
            return None
