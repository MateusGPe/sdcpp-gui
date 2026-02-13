"""
Service for managing 'Sidecar' files (JSON metadata and Preview images).
"""

import json
import os
from typing import Any, Dict

import requests

from sd_cpp_gui.data.db.settings_manager import SettingsManager
from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)


class SidecarService:
    def __init__(self, settings: SettingsManager):
        """Logic: Initializes service."""
        self.settings = settings

    def save_metadata(
        self, base_file_path: str, metadata: Dict[str, Any], suffix: str = ""
    ) -> None:
        """
        Saves metadata to a JSON file next to the model.
        Args:
            base_file_path: /path/to/model.safetensors
            metadata: The dict to save.
            suffix: Optional suffix (e.g., ".model" for model.model.json).
        """
        base_name = os.path.splitext(base_file_path)[0]
        json_path = f"{base_name}{suffix}.json"
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)
            logger.debug(f"Saved metadata: {json_path}")
        except IOError as e:
            logger.error(f"Failed to save sidecar {json_path}: {e}")

    def download_preview(self, base_file_path: str, image_url: str) -> None:
        """
        Downloads a preview image next to the model, handling API Auth.
        """
        if not image_url:
            return
        base_name = os.path.splitext(base_file_path)[0]
        for ext in [".preview.png", ".preview.jpg", ".png", ".jpg"]:
            if os.path.exists(f"{base_name}{ext}"):
                return
        dest_path = f"{base_name}.preview.png"
        headers = {}
        api_key = self.settings.get_str("civitai_api_key", "")
        if api_key and "civitai.com" in image_url:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            with requests.get(
                image_url, headers=headers, stream=True, timeout=15
            ) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logger.debug(f"Saved preview: {dest_path}")
        except Exception as e:
            logger.warning(f"Failed to download preview from {image_url}: {e}")
