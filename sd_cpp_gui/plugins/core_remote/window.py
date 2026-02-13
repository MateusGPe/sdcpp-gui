"""
Remote Model Browser Window.
Aggregates modular tabs and panels.
"""

from __future__ import annotations

import os
from tkinter import BOTH, X, messagebox
from typing import TYPE_CHECKING, Any, Dict

import ttkbootstrap as ttk

from sd_cpp_gui.domain.services.image_loader import ImageLoader
from sd_cpp_gui.infrastructure.event_bus import EventBus
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components.utils import CopyLabel, center_window

from .helpers import OwnershipChecker
from .tabs.config import ConfigTab
from .tabs.downloads import DownloadsTab
from .tabs.hash_lookup import HashLookupTab
from .tabs.search import SearchTab

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer
    from sd_cpp_gui.infrastructure.i18n import I18nManager
    from sd_cpp_gui.ui.app import App

i18n: I18nManager = get_i18n()


class RemoteBrowserWindow(ttk.Toplevel):
    """Window for browsing and downloading remote models."""

    def __init__(self, parent: App, container: DependencyContainer) -> None:
        """Initializes the browser window.

        Logic: Sets up dependencies, managers, image loader,
        layout, and event subscriptions."""
        super().__init__(master=parent)
        self.title(i18n.get("remote.window.title", "Remote Model Browser"))
        self.geometry("1280x900")
        self.remote = container.remote
        self.settings = container.settings
        self.managers = {
            "Checkpoint": container.models,
            "LoRA": container.loras,
            "Embedding": container.embeddings,
        }
        self.ownership = OwnershipChecker(
            container.models, container.loras, container.embeddings
        )
        self.current_provider = "civitai"
        self.img_loader = ImageLoader()
        self._init_ui()
        center_window(self, parent, 1280, 900)  # type: ignore
        self.check_api_key()
        EventBus.subscribe(
            "remote_download_complete",
            str(id(self)),
            self._on_remote_download_complete,  # type: ignore
        )
        EventBus.subscribe(
            "download_progress",
            str(id(self)),
            self._on_download_progress,  # type: ignore
        )
        EventBus.subscribe(
            "download_error",
            str(id(self)),
            self._on_download_error,  # type: ignore
        )

    def destroy(self) -> None:
        """Cleans up resources.

        Logic: Stops image loader, cleans up tabs, unsubscribes events,
        and destroys window."""
        self.img_loader.stop()
        if hasattr(self, "tab_hash") and isinstance(
            self.tab_hash, HashLookupTab
        ):
            self.tab_hash.destroy()
        EventBus.unsubscribe("remote_download_complete", str(id(self)))
        EventBus.unsubscribe("download_progress", str(id(self)))
        EventBus.unsubscribe("download_error", str(id(self)))
        super().destroy()

    def check_api_key(self) -> None:
        """Warns the user if no API key is detected.

        Logic: Checks settings for API key and updates search
        tab warning visibility."""
        key = self.settings.get("civitai_api_key", "")
        has_key = bool(key)
        self.tab_search.toggle_api_warning(not has_key)

    def _init_ui(self) -> None:
        """Builds the UI layout.

        Logic: Creates Status bar and Notebook tabs (Search,
        Hash, Downloads, Config)."""
        self.status_bar = CopyLabel(
            self,
            text=i18n.get("remote.status.ready", "Ready"),
            bootstyle="secondary",
            anchor="w",
            padding=(5, 2),
        )
        self.status_bar.pack(side="bottom", fill=X)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.tab_search = SearchTab(self.notebook, self)
        self.notebook.add(
            self.tab_search, text=i18n.get("remote.tab.search", "🔍 Search")
        )
        self.tab_hash = HashLookupTab(self.notebook, self)
        self.notebook.add(
            self.tab_hash,
            text=i18n.get("remote.tab.hash", "#️⃣ Hash Lookup"),
        )
        self.tab_downloads = DownloadsTab(self.notebook, self)
        self.notebook.add(
            self.tab_downloads,
            text=i18n.get("remote.tab.downloads", "⬇ Downloads"),
        )
        self.tab_config = ConfigTab(self.notebook, self)
        self.notebook.add(
            self.tab_config, text=i18n.get("remote.tab.config", "⚙️ Config")
        )

    def _on_download_progress(self, data: Dict[str, Any]) -> None:
        """Updates download progress in the Downloads Tab.

        Logic: Forwards progress data to the downloads tab via main thread."""
        if not self.winfo_exists():
            return
        self.after(0, lambda: self.tab_downloads.update_progress(data))

    def _on_download_error(self, data: Dict[str, Any]) -> None:
        """Logic: Schedules error display on main thread."""
        if not self.winfo_exists():
            return
        url = data["url"]
        error = data["error"]
        self.after(0, lambda: self._show_download_error(url, error))

    def _show_download_error(self, url: str, error: str) -> None:
        """Logic: Updates status bar and shows error message box."""
        msg = i18n.get(
            "remote.status.download_failed", "Download failed: {error}"
        ).format(error=error)
        self.status_bar.configure(text=msg, bootstyle="danger")
        messagebox.showerror(
            i18n.get("status.error", "Error"),
            f"URL: {url}\nError: {error}",
            parent=self,
        )

    def _on_remote_download_complete(self, data: Dict[str, Any]) -> None:
        """
        Listener: When a download completes with metadata, update the DB.
        Logic: Schedules completion handling on main thread."""
        if not self.winfo_exists():
            return
        self.after(0, lambda: self._complete_download_ui(data))

    def get_manager_by_type(self, raw_type: str) -> Any:
        """
        Returns the appropriate manager for a given model type string.
        Handles mapping from API types (TextualInversion) to internal
        keys (Embedding).

        Logic: Maps API type string to internal manager instance."""
        mapping = {
            "checkpoint": "Checkpoint",
            "lora": "LoRA",
            "textualinversion": "Embedding",
            "embedding": "Embedding",
        }
        key = mapping.get(str(raw_type).lower(), "Checkpoint")
        return self.managers.get(key, self.managers["Checkpoint"])

    def _complete_download_ui(self, data: Dict[str, Any]) -> None:
        """Logic: Registers the downloaded model in the appropriate manager,
        shows success msg, updates status, and refreshes UI."""
        path = data["path"]
        metadata = data["metadata"]
        m_type_str = metadata.get("type", "Checkpoint")
        manager = self.get_manager_by_type(m_type_str)
        if hasattr(manager, "register_from_remote"):
            manager.register_from_remote(path, metadata)

        status_msg = i18n.get(
            "remote.status.installed", "Installed: {filename}"
        ).format(filename=os.path.basename(path))
        self.status_bar.configure(text=status_msg, bootstyle="success")

        title = i18n.get("remote.msg.download_complete", "Download Complete")
        msg = i18n.get("remote.msg.installed_model", "Installed {name}").format(
            name=metadata["name"]
        )
        messagebox.showinfo(title, msg, parent=self)

        self.ownership.refresh()
        det = self.tab_search.details_content
        if det.current_version_data and str(
            det.current_version_data["id"]
        ) == str(metadata["id"]):
            det.btn_download.configure(
                text=i18n.get("remote.details.btn_installed", "✅ Installed"),
                state="disabled",
                bootstyle="secondary",
            )
