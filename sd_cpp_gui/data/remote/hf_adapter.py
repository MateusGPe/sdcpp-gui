from typing import Any, List, Optional, Set

from sd_cpp_gui.data.remote.remote import IRemoteRepository
from sd_cpp_gui.data.remote.types import (
    RemoteFileDTO,
    RemoteModelDTO,
    RemoteVersionDTO,
)
from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)
try:
    from huggingface_hub import HfApi
    from huggingface_hub.hf_api import ModelInfo

    HAS_HF = True
except ImportError:
    HAS_HF = False
    HfApi = Any  # type: ignore
    ModelInfo = Any  # type: ignore


class HuggingFaceAdapter(IRemoteRepository):
    """
    Adapter for Hugging Face Models.
    Requires `huggingface_hub` package.
    """

    def __init__(self, api_token: Optional[str] = None) -> None:
        """Logic: Initializes HF API client if library is available."""
        if not HAS_HF:
            logger.warning(
                "huggingface_hub library not installed."
                " HF integration disabled."
            )
            self.api = None
        else:
            self.api = HfApi(token=api_token)

    def _determine_type(self, tags: List[str]) -> str:
        """Heuristic to determine model type from HF tags.

        Logic: Infers model type from tags."""
        tags_set = set((t.lower() for t in tags))
        if "lora" in tags_set:
            return "LoRA"
        if "controlnet" in tags_set:
            return "ControlNet"
        if "textual-inversion" in tags_set:
            return "Embedding"
        if "text-to-image" in tags_set:
            return "Checkpoint"
        return "Checkpoint"

    def _map_to_dto(self, raw: ModelInfo) -> RemoteModelDTO:
        """Maps HF ModelInfo to generic DTO.

        Logic: Maps HF model info to local DTO."""
        tags = raw.tags or []
        likes = raw.likes or 0
        rating = 0.0
        if likes > 0:
            rating = min(5.0, 3.0 + likes / 1000.0)
        return {
            "id": raw.id,
            "name": raw.id.split("/")[-1],
            "creator": raw.author or raw.id.split("/")[0],
            "image_url": None,
            "type": self._determine_type(tags),
            "nsfw": False,
            "tags": tags,
            "download_count": raw.downloads or 0,
            "rating": rating,
            "base_model": None,
            "description": None,
            "versions": [
                {
                    "id": raw.id,
                    "name": "Main",
                    "base_model": None,
                    "published_at": None,
                }
            ],
        }

    def _map_to_version_dto(self, raw: ModelInfo) -> RemoteVersionDTO:
        """Maps HF ModelInfo to generic Version DTO.

        Logic: Maps HF model info to local Version DTO."""
        files: List[RemoteFileDTO] = []
        relevant: Set[str] = {".safetensors", ".ckpt", ".pt", ".bin"}
        if raw.siblings:
            for f in raw.siblings:
                if any((f.rfilename.endswith(ext) for ext in relevant)):
                    dl_url = f"https://huggingface.co/{raw.id}/resolve/main/{f.rfilename}"
                    is_primary = f.rfilename.endswith(".safetensors")
                    files.append(
                        {
                            "id": f.rfilename,
                            "name": f.rfilename,
                            "size_kb": 0,
                            "download_url": dl_url,
                            "primary": is_primary,
                            "hashes": {},
                            "pickle_scan_result": "Success",
                            "virus_scan_result": "Success",
                        }
                    )
        files.sort(key=lambda x: x["primary"], reverse=True)
        dl_url = files[0]["download_url"] if files else ""
        return {
            "id": raw.id,
            "model_id": raw.id,
            "name": "Latest (Main Branch)",
            "description": f"HuggingFace Repository: {raw.id}",
            "trigger_words": [],
            "files": files,
            "images": [],
            "base_model": "Unknown",
            "published_at": "",
            "download_url": dl_url,
            "stats": {},
        }

    def search_models(
        self,
        query: str,
        model_type: Optional[str] = None,
        base_model: Optional[str] = None,
        page: int = 1,
        nsfw: bool = False,
    ) -> List[RemoteModelDTO]:
        """Logic: Performs search on HF hub."""
        if not self.api:
            return []
        tags = ["text-to-image"]
        if model_type == "LoRA":
            tags.append("lora")
        elif model_type == "ControlNet":
            tags.append("controlnet")
        elif model_type == "Embedding":
            tags.append("textual-inversion")
        if base_model and base_model != "All":
            if "SD 1.5" in base_model:
                tags.append("stable-diffusion")
            elif "SDXL" in base_model:
                tags.append("stable-diffusion-xl")
        limit = 20
        try:
            results = self.api.list_models(
                search=query,
                filter=tags,
                sort="downloads",
                direction=-1,
                limit=limit,
                full=False,
            )
            return [self._map_to_dto(item) for item in results]
        except Exception as e:
            logger.error("HF Search error: %s", e)
            return []

    def get_model_details(self, model_id: str) -> Optional[RemoteModelDTO]:
        """Logic: Fetches HF repo info."""
        if not self.api:
            return None
        try:
            info = self.api.model_info(repo_id=model_id)
            return self._map_to_dto(info)
        except Exception:
            return None

    def get_version_details(
        self, version_id: str
    ) -> Optional[RemoteVersionDTO]:
        """
        Logic: Fetches HF repo info (version logic is mostly same
        as model for HF).
        """
        if not self.api:
            return None
        try:
            info = self.api.model_info(repo_id=version_id, files_metadata=False)
            return self._map_to_version_dto(info)
        except Exception:
            return None

    def get_version_by_hash(self, file_hash: str) -> Optional[RemoteVersionDTO]:
        """Logic: Not implemented for HF."""
        return None
