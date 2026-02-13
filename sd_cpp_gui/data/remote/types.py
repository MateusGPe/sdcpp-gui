"""
Type definitions for Remote Repository interactions.
"""

from typing import Any, Dict, List, Optional, TypedDict


class RemoteFileDTO(TypedDict):
    """Generic representation of a downloadable file."""

    id: str
    name: str
    size_kb: float
    download_url: str
    primary: bool
    pickle_scan_result: Optional[str]
    virus_scan_result: Optional[str]
    hashes: Dict[str, str]


class RemoteImageDTO(TypedDict):
    """Representation of a gallery image."""

    url: str
    nsfw: bool
    width: int
    height: int
    meta: Optional[Dict[str, Any]]  # Generation metadata


class RemoteVersionSummary(TypedDict):
    """Lightweight version info for listing in dropdowns."""

    id: str
    name: str
    base_model: Optional[str]
    published_at: Optional[str]


class RemoteVersionDTO(TypedDict):
    """Detailed representation of a specific model version."""

    id: str
    model_id: str
    name: str
    description: str
    base_model: str
    published_at: str
    trigger_words: List[str]
    files: List[RemoteFileDTO]
    images: List[RemoteImageDTO]
    download_url: str  # URL of the primary file for quick access
    stats: Dict[str, int]  # downloadCount, ratingCount, etc.


class RemoteModelDTO(TypedDict):
    """Generic representation of a model for the search grid."""

    id: str
    name: str
    creator: str
    image_url: Optional[str]
    type: str
    nsfw: bool
    tags: List[str]
    download_count: int
    rating: float
    base_model: Optional[str]  # Derived from latest version if possible
    description: Optional[str]
    versions: List[RemoteVersionSummary]
