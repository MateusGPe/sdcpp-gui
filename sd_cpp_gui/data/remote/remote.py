from abc import ABC, abstractmethod
from typing import List, Optional

from sd_cpp_gui.data.remote.types import RemoteModelDTO, RemoteVersionDTO


class IRemoteRepository(ABC):
    """
    Abstract Base Class that any Model Provider (Civitai, HF) must implement.
    """

    @abstractmethod
    def search_models(
        self,
        query: str,
        model_type: Optional[str] = None,
        base_model: Optional[str] = None,
        page: int = 1,
        nsfw: bool = False,
    ) -> List[RemoteModelDTO]:
        """
        Searches for models in the remote repository.

        Args:
                query: The search term.
                model_type: Filter by type (e.g., 'Checkpoint', 'LoRA').
                base_model: Filter by base architecture.
                page: Pagination index (1-based).
                nsfw: Whether to include NSFW results.

        Returns:
                A list of standardized model DTOs.
        """
        pass

    @abstractmethod
    def get_model_details(self, model_id: str) -> Optional[RemoteModelDTO]:
        """
        Gets metadata for a specific model.

        Args:
                model_id: The unique identifier of the model.

        Returns:
                The model DTO or None if not found.
        """
        pass

    @abstractmethod
    def get_version_details(
        self, version_id: str
    ) -> Optional[RemoteVersionDTO]:
        """
        Gets details about a specific version (files, triggers).

        Args:
                version_id: The unique identifier of the version.

        Returns:
                The version DTO or None if not found.
        """
        pass

    @abstractmethod
    def get_version_by_hash(self, file_hash: str) -> Optional[RemoteVersionDTO]:
        """
        Finds a model version based on a local file hash (SHA256).

        Args:
                file_hash: The SHA256 hash string.

        Returns:
                The version DTO or None if not found.
        """
        pass
