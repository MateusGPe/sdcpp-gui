"""
Low-level client for Civitai API.
"""

import json
import logging
import time
from enum import Enum
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
    cast,
)
from urllib.parse import parse_qs, urlparse

import requests
from requests.exceptions import HTTPError

from sd_cpp_gui.infrastructure.paths import DATA_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Sort(str, Enum):
    """Sort options for models and images."""

    HIGHEST_RATED = "Highest Rated"
    MOST_DOWNLOADED = "Most Downloaded"
    NEWEST = "Newest"
    MOST_REACTIONS = "Most Reactions"
    MOST_COMMENTS = "Most Comments"


class Period(str, Enum):
    """Time period options."""

    ALL_TIME = "AllTime"
    YEAR = "Year"
    MONTH = "Month"
    WEEK = "Week"
    DAY = "Day"


class ModelType(str, Enum):
    """Supported model types."""

    CHECKPOINT = "Checkpoint"
    TEXTUAL_INVERSION = "TextualInversion"
    HYPERNETWORK = "Hypernetwork"
    AESTHETIC_GRADIENT = "AestheticGradient"
    LORA = "LORA"
    CONTROLNET = "Controlnet"
    POSES = "Poses"
    WILDCARDS = "Wildcards"
    OTHER = "Other"


class CreatorDict(TypedDict):
    username: str
    image: Optional[str]


class FileDict(TypedDict):
    name: str
    id: int
    sizeKb: float
    type: str
    metadata: Dict[str, Any]
    pickleScanResult: str
    virusScanResult: str
    scannedAt: Optional[str]
    hashes: Dict[str, str]
    primary: Optional[bool]
    downloadUrl: str


class ImageMetaDict(TypedDict, total=False):
    Size: str
    seed: int
    Model: str
    steps: int
    prompt: str
    sampler: str
    cfgScale: float
    negativePrompt: str


class ImageDict(TypedDict):
    id: int
    url: str
    hash: str
    width: int
    height: int
    nsfw: bool
    nsfwLevel: Union[int, str]
    createdAt: str
    postId: Optional[int]
    stats: Dict[str, int]
    meta: Optional[ImageMetaDict]
    username: str


class ModelVersionDict(TypedDict):
    id: int
    modelId: int
    name: str
    createdAt: str
    updatedAt: str
    trainedWords: List[str]
    baseModel: str
    earlyAccessTimeFrame: int
    description: Optional[str]
    files: List[FileDict]
    images: List[ImageDict]
    downloadUrl: str


class ModelDict(TypedDict):
    id: int
    name: str
    description: str
    type: str
    poi: bool
    nsfw: bool
    allowNoCredit: bool
    allowCommercialUse: str
    allowDerivatives: bool
    allowDifferentLicense: bool
    stats: Dict[str, int]
    creator: CreatorDict
    tags: List[str]
    modelVersions: List[ModelVersionDict]


class MetadataDict(TypedDict):
    totalItems: int
    currentPage: int
    pageSize: int
    totalPages: int
    nextPage: Optional[str]
    prevPage: Optional[str]
    nextCursor: Optional[str]


class PaginatedResponse(TypedDict):
    items: List[Any]
    metadata: MetadataDict


class UrlMetaDict(TypedDict):
    type: Literal["model", "image", "unknown"]
    model_id: Optional[int]
    version_id: Optional[int]
    original_url: str


KNOWN_BASE_MODELS = [
    "All",
    "AuraFlow",
    "Chroma",
    "CogVideoX",
    "Flux.1 D",
    "Flux.1 Kontext",
    "Flux.1 Krea",
    "Flux.1 S",
    "Flux.2 D",
    "HiDream",
    "Hunyuan 1",
    "Hunyuan Video",
    "Illustrious",
    "Imagen4",
    "Kolors",
    "LTXV",
    "Lumina",
    "Mochi",
    "Nano Banana",
    "NoobAI",
    "ODOR",
    "OpenAI",
    "Other",
    "PixArt E",
    "PixArt a",
    "Playground v2",
    "Pony",
    "Pony V7",
    "Qwen",
    "SD 1.4",
    "SD 1.5",
    "SD 1.5 Hyper",
    "SD 1.5 LCM",
    "SD 2.0",
    "SD 2.0 768",
    "SD 2.1",
    "SD 2.1 768",
    "SD 2.1 Unclip",
    "SD 3",
    "SD 3.5",
    "SD 3.5 Large",
    "SD 3.5 Large Turbo",
    "SD 3.5 Medium",
    "SDXL 0.9",
    "SDXL 1.0",
    "SDXL 1.0 LCM",
    "SDXL Distilled",
    "SDXL Hyper",
    "SDXL Lightning",
    "SDXL Turbo",
    "SVD",
    "SVD XT",
    "Seedream",
    "Sora 2",
    "Stable Cascade",
    "Veo 3",
    "Wan Video",
    "Wan Video 1.3B t2v",
    "Wan Video 14B i2v 480p",
    "Wan Video 14B i2v 720p",
    "Wan Video 14B t2v",
    "Wan Video 2.2 I2V-A14B",
    "Wan Video 2.2 T2V-A14B",
    "Wan Video 2.2 TI2V-5B",
    "Wan Video 2.5 I2V",
    "Wan Video 2.5 T2V",
    "ZImageTurbo",
    "Others",
]


class CivitaiClient:
    """
    A Python client for the Civitai Public REST API.
    Documentation: https://developer.civitai.com/docs/api/public-rest
    """

    BASE_URL: str = "https://civitai.com/api/v1"

    def __init__(
        self, api_token: Optional[str] = None, timeout: int = 10
    ) -> None:
        """
        Initialize the Civitai client.

        Args:
            api_token: Your Civitai API Key. Required for accessing NSFW
                       content or user-specific data (favorites).
            timeout: The timeout for requests in seconds.

        Logic: Initializes session, headers, and API token.
        """
        self.session = requests.Session()
        self.timeout = timeout
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "User-Agent": "SDCppGUI/1.0",
            }
        )
        if api_token:
            auth_header = {"Authorization": f"Bearer {api_token}"}
            self.session.headers.update(auth_header)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 3,
    ) -> Any:
        """Internal method to handle API requests and error checking.

        Logic: Handles HTTP requests, retries, and error mapping."""
        url = f"{self.BASE_URL}{endpoint}"
        clean_params: Dict[str, Any] = {}
        if params:
            for k, v in params.items():
                if v is None:
                    continue
                if isinstance(v, bool):
                    clean_params[k] = str(v).lower()
                elif isinstance(v, Enum):
                    clean_params[k] = v.value
                else:
                    clean_params[k] = v
        for attempt in range(retries):
            try:
                response = self.session.request(
                    method, url, params=clean_params, timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except HTTPError as e:
                code = e.response.status_code if e.response else 0
                if code == 429 and attempt < retries - 1:
                    sleep_time = (2**attempt) + 1
                    logger.warning(
                        f"Rate limited (429). Retrying in {sleep_time}s..."
                    )
                    time.sleep(sleep_time)
                    continue
                if code == 401:
                    raise PermissionError(
                        "API Key Invalid or Missing (401)."
                        " Please check settings."
                    )
                elif code == 403:
                    raise PermissionError(
                        "Access Denied (403)."
                        " Content may be strictly restricted."
                    )
                elif code == 429:
                    raise ConnectionError("Rate Limit Exceeded (429).")
                elif code >= 500:
                    raise ConnectionError(f"Civitai Server Error ({code}).")
                else:
                    raise ConnectionError(f"HTTP Error {code}: {e}")
            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"Network Error: {str(e)}")

    def get_models(
        self,
        limit: int = 100,
        page: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        username: Optional[str] = None,
        types: Optional[Union[ModelType, List[ModelType]]] = None,
        sort: Optional[Sort] = None,
        period: Optional[Period] = None,
        rating: Optional[int] = None,
        favorites: bool = False,
        hidden: bool = False,
        primary_file_only: bool = False,
        nsfw: bool = True,
        base_model: Optional[str] = None,
    ) -> PaginatedResponse:
        """Get a list of models.

        Logic: Calls /models endpoint with filters."""
        params: Dict[str, Any] = {
            "limit": limit,
            "query": query,
            "tag": tag,
            "username": username,
            "rating": rating,
            "sort": sort,
            "period": period,
            "favorites": favorites,
            "hidden": hidden,
            "primaryFileOnly": primary_file_only,
            "nsfw": nsfw,
            "baseModels": base_model,
        }
        if query:
            params["cursor"] = cursor
        else:
            params["page"] = page
        if types:
            if isinstance(types, list):
                params["types"] = [t.value for t in types]
            else:
                params["types"] = types.value
        return cast(
            PaginatedResponse, self._request("GET", "/models", params=params)
        )

    def get_creators(
        self, limit: int = 20, page: int = 1, query: Optional[str] = None
    ) -> PaginatedResponse:
        """Get a list of creators.

        Logic: Calls /creators endpoint."""
        params: Dict[str, Any] = {"limit": limit, "page": page, "query": query}
        return cast(
            PaginatedResponse, self._request("GET", "/creators", params=params)
        )

    def get_model(self, model_id: int) -> ModelDict:
        """Get detailed information about a specific model by ID.

        Logic: Calls /models/{id} endpoint."""
        return cast(ModelDict, self._request("GET", f"/models/{model_id}"))

    def get_model_version(self, version_id: int) -> ModelVersionDict:
        """Get detailed information about a specific model version by ID.

        Logic: Calls /model-versions/{id} endpoint."""
        return cast(
            ModelVersionDict,
            self._request("GET", f"/model-versions/{version_id}"),
        )

    def get_model_version_by_hash(self, file_hash: str) -> ModelVersionDict:
        """Get model version details by file hash.

        Logic: Calls /model-versions/by-hash/{hash} endpoint."""
        return cast(
            ModelVersionDict,
            self._request("GET", f"/model-versions/by-hash/{file_hash}"),
        )

    def get_images(
        self,
        limit: int = 100,
        page: int = 1,
        post_id: Optional[int] = None,
        model_id: Optional[int] = None,
        model_version_id: Optional[int] = None,
        username: Optional[str] = None,
        sort: Optional[Sort] = None,
        period: Optional[Period] = None,
        nsfw: Optional[
            Union[bool, Literal["None", "Soft", "Mature", "X"]]
        ] = None,
    ) -> PaginatedResponse:
        """
        Get a list of images with filters.
        Args:
            nsfw: Filter for NSFW content. Can be a boolean or specific enum
            string (None, Soft, Mature, X) depending on endpoint version.

        Logic: Calls /images endpoint."""
        params: Dict[str, Any] = {"limit": limit, "page": page}
        if post_id:
            params["postId"] = post_id
        if model_id:
            params["modelId"] = model_id
        if model_version_id:
            params["modelVersionId"] = model_version_id
        if username:
            params["username"] = username
        if sort:
            params["sort"] = sort
        if period:
            params["period"] = period
        if nsfw is not None:
            params["nsfw"] = nsfw
        return cast(
            PaginatedResponse, self._request("GET", "/images", params=params)
        )

    def get_tags(
        self, limit: int = 100, page: int = 1, query: Optional[str] = None
    ) -> PaginatedResponse:
        """Get a list of tags.

        Logic: Calls /tags endpoint."""
        params: Dict[str, Any] = {"limit": limit, "page": page}
        if query:
            params["query"] = query
        return cast(
            PaginatedResponse, self._request("GET", "/tags", params=params)
        )

    def iterate_models(self, **kwargs: Any) -> Generator[ModelDict, None, None]:
        """
        Smart generator that automatically switches between Page-based and
        Cursor-based pagination depending on whether a search query is used.

        Logic: Generator that handles pagination (cursor or page based)
        automatically.
        """
        current_page: int = 1
        current_cursor: Optional[str] = None
        is_search: bool = kwargs.get("query") is not None
        while True:
            if is_search:
                kwargs["cursor"] = current_cursor
                if "page" in kwargs:
                    del kwargs["page"]
            else:
                kwargs["page"] = current_page
                if "cursor" in kwargs:
                    del kwargs["cursor"]
            data: PaginatedResponse = self.get_models(**kwargs)
            items: List[ModelDict] = data.get("items", [])
            if not items:
                break
            for item in items:
                yield item
            meta: MetadataDict = data.get("metadata", {})  # type: ignore
            if is_search:
                next_cursor: Optional[str] = meta.get("nextCursor")
                if not next_cursor:
                    break
                current_cursor = next_cursor
            else:
                total_pages = meta.get("totalPages", 0)
                if current_page >= total_pages:
                    break
                current_page += 1


def parse_civitai_url(url: str) -> UrlMetaDict:
    """Extracts type, model_id, and version_id from a Civitai URL.

    Logic: Parses URL string to extract model ID, version ID, and type."""
    parsed = urlparse(url.strip())
    path_parts: List[str] = parsed.path.strip("/").split("/")
    query_params: Dict[str, List[str]] = parse_qs(parsed.query)
    result: UrlMetaDict = {
        "type": "unknown",
        "model_id": None,
        "version_id": None,
        "original_url": url.strip(),
    }
    if len(path_parts) >= 2 and path_parts[0] == "models":
        if path_parts[1].isdigit():
            result["type"] = "model"
            result["model_id"] = int(path_parts[1])
            if "modelVersionId" in query_params:
                try:
                    result["version_id"] = int(
                        query_params["modelVersionId"][0]
                    )
                except (ValueError, IndexError):
                    pass
    elif len(path_parts) >= 2 and path_parts[0] == "images":
        result["type"] = "image"
    return result


def process_model_list(
    file_path: str, output_path: str, api_token: Optional[str] = None
) -> None:
    """
    Logic: Utility to batch process a text file of URLs and
    save metadata JSONs.
    """
    client: CivitaiClient = CivitaiClient(api_token)
    urls: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return
    total: int = len(urls)
    logger.info(f"Found {total} URLs to process...")
    for i, url in enumerate(urls):
        meta: UrlMetaDict = parse_civitai_url(url)
        if meta["type"] == "image":
            logger.info(f"[{i + 1}/{total}] Skipping Image URL: {url}")
            continue
        if meta["type"] != "model" or not meta["model_id"]:
            logger.warning(f"[{i + 1}/{total}] Could not parse Model ID: {url}")
            continue
        try:
            data: Union[ModelDict, ModelVersionDict, None] = None
            if meta["version_id"]:
                data = client.get_model_version(meta["version_id"])
            else:
                data = client.get_model(meta["model_id"])  # type: ignore
            if data:
                output_data = cast(Dict[str, Any], data)
                output_data["_extraction_meta"] = meta
                try:
                    jsons_dir = DATA_DIR / "jsons"
                    jsons_dir.mkdir(parents=True, exist_ok=True)
                    save_path = jsons_dir / f"{meta['model_id']}.json"
                    with open(save_path, "w", encoding="utf-8") as f:
                        json.dump(output_data, f, indent=2, ensure_ascii=False)
                    logger.info(f"Successfully saved to {save_path}")
                except Exception as e:
                    logger.error(f"Failed to save JSON: {e}")
            else:
                logger.warning(f"Failed to fetch data: {url}")
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
        time.sleep(1)
