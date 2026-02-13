"""
Updated LibraryScanner to download preview images.
"""

import hashlib
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from sd_cpp_gui.data.remote.remote_manager import RemoteManager


class LibraryScanner:
    """
    Handles bulk scanning of local files to calculate hashes and find
    remote metadata.
    """

    def __init__(
        self,
        managers: Dict[str, Any],
        remote: RemoteManager,
        progress_cb: Callable[[float], None],
        status_cb: Callable[[str], None],
        finish_cb: Callable[[int, int], None],
    ) -> None:
        """
        Initializes the scanner.

        Args:
            managers: Dictionary of data managers (ModelManager, LoraManager,
            etc.).
            remote: The remote manager instance for API lookups.
            progress_cb: Callback for progress percentage (0.0 to 100.0).
            status_cb: Callback for text status updates.
            finish_cb: Callback executed when scanning completes
            (success_count, total).

        Logic: Initializes scanner with dependencies and callbacks.
        """
        self.managers = managers
        self.remote = remote
        self.progress_cb = progress_cb
        self.status_cb = status_cb
        self.finish_cb = finish_cb
        self.stop_event = threading.Event()

    def start(self, scan_all: bool = False) -> None:
        """
        Starts the scanning process in a separate thread.

        Args:
            scan_all: If True, rescans files that already have remote metadata.

        Logic: Starts worker thread.
        """
        threading.Thread(
            target=self._worker, args=(scan_all,), daemon=True
        ).start()

    def stop(self) -> None:
        """Signals the scanning thread to stop.

        Logic: Sets stop event."""
        self.stop_event.set()

    def _worker(self, scan_all: bool) -> None:
        """
        Background worker logic.
        Args:
            scan_all: Whether to force rescan of all items.

        Logic: Iterates over files, calculates hash, fetches metadata,
        saves sidecars, and updates DB.
        """
        items_to_scan: List[Tuple[str, str, Any]] = []
        self.status_cb("Collecting files...")
        for m_type, mgr in self.managers.items():
            for item in mgr.get_all():
                remote_id = (
                    item.get("remote_id")
                    if isinstance(item, dict)
                    else getattr(item, "remote_id", None)
                )
                path = (
                    item.get("path")
                    if isinstance(item, dict)
                    else getattr(item, "path", "")
                )
                if not scan_all and remote_id:
                    continue
                if path and os.path.exists(path):
                    items_to_scan.append((m_type, path, mgr))
        total = len(items_to_scan)
        if total == 0:
            self.finish_cb(0, 0)
            return
        success_count = 0
        for i, (_, path, mgr) in enumerate(items_to_scan):
            if self.stop_event.is_set():
                break
            fname = os.path.basename(path)
            self.status_cb(f"Scanning [{i + 1}/{total}]: {fname}")
            self.progress_cb(i / total * 100)
            try:
                sha256 = self._calc_hash(path)
                if not sha256:
                    continue
                if hasattr(mgr, "update_hash"):
                    mgr.update_hash(path, sha256)
                version_dto = self.remote.fetch_rich_metadata(hash_value=sha256)
                if version_dto:
                    self.remote.sidecar.save_metadata(path, version_dto)
                    if "_parent_model" in version_dto:
                        self.remote.sidecar.save_metadata(
                            path, version_dto["_parent_model"], suffix=".model"
                        )  # type: ignore
                    if version_dto.get("images"):
                        preview_url = version_dto["images"][0].get("url")
                        if preview_url:
                            self.remote.sidecar.download_preview(
                                path, preview_url
                            )
                    if hasattr(mgr, "register_from_remote"):
                        mgr.register_from_remote(
                            path, version_dto, hash_value=sha256
                        )
                        success_count += 1
            except Exception as e:
                print(f"Error scanning {fname}: {e}")
        self.progress_cb(100.0)
        self.finish_cb(success_count, total)

    def _calc_hash(self, path: str) -> Optional[str]:
        """Calculates SHA256 hash.

        Logic: Calculates file SHA256 hash in chunks."""
        sha256 = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1048576), b""):
                    if self.stop_event.is_set():
                        return None
                    sha256.update(chunk)
            return sha256.hexdigest().upper()
        except (OSError, IOError):
            return None
