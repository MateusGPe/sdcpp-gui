"""
Download Manager.
Handles asynchronous file downloads with progress reporting via EventBus.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional

import requests

from sd_cpp_gui.infrastructure.event_bus import EventBus
from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)


class DownloadManager:
    """
    Manages concurrent downloads in background threads using a ThreadPool.
    """

    def __init__(self, max_workers: int = 2) -> None:
        """Logic: Initializes thread pool and state tracking."""
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_downloads: Dict[str, bool] = {}
        self._lock = threading.Lock()

    def start_download(
        self,
        url: str,
        dest_folder: str,
        filename: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Starts a download in a background thread.

        Args:
            url: The file URL.
            dest_folder: The destination directory.
            filename: Optional filename. If None, derived from URL.
            callback: Optional function to call on completion (arg: full_path).
            headers: Optional HTTP headers (e.g. for Authorization).

        Logic: Submits download task to thread pool.
        """
        with self._lock:
            if url in self.active_downloads:
                logger.warning("Download already active for: %s", url)
                return
        if not filename:
            filename = url.split("/")[-1].split("?")[0]
            if not filename:
                filename = "downloaded_model.safetensors"
        dest_path = os.path.join(dest_folder, filename)
        os.makedirs(dest_folder, exist_ok=True)
        with self._lock:
            self.active_downloads[url] = True
        self.executor.submit(
            self._download_worker, url, dest_path, callback, headers
        )
        EventBus.publish("download_started", {"url": url, "filename": filename})

    def cancel_download(self, url: str) -> None:
        """Signals a download to stop.

        Logic: Flags download for cancellation."""
        with self._lock:
            if url in self.active_downloads:
                self.active_downloads[url] = False

    def _download_worker(
        self,
        url: str,
        dest_path: str,
        callback: Optional[Callable[[str], None]],
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Internal worker function.
        Logic: Downloads file stream, updates progress via EventBus,
        handles cancellation.
        """
        try:
            logger.info("Starting download: %s -> %s", url, dest_path)
            with requests.get(
                url,
                stream=True,
                allow_redirects=True,
                timeout=20,
                headers=headers,
            ) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("content-length", 0))
                downloaded = 0
                should_delete = False
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        with self._lock:
                            if not self.active_downloads.get(url, False):
                                logger.info("Download cancelled: %s", url)
                                should_delete = True
                                break
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            percent = (
                                downloaded / total_size * 100
                                if total_size > 0
                                else 0
                            )
                            EventBus.publish(
                                "download_progress",
                                {
                                    "url": url,
                                    "filename": os.path.basename(dest_path),
                                    "current": downloaded,
                                    "total": total_size,
                                    "percent": percent,
                                },
                            )
                        if should_delete:
                            break
            if should_delete:
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                return
            logger.info("Download finished: %s", dest_path)
            with self._lock:
                if url in self.active_downloads:
                    del self.active_downloads[url]
            EventBus.publish(
                "download_finished", {"url": url, "path": dest_path}
            )
            if callback:
                callback(dest_path)
        except Exception as e:
            logger.error("Download failed: %s", e)
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            with self._lock:
                if url in self.active_downloads:
                    del self.active_downloads[url]
            EventBus.publish("download_error", {"url": url, "error": str(e)})
