"""
Updated HashLookupTab with API Key authentication for preview downloads.
"""

from __future__ import annotations

import hashlib
import os
import threading
import tkinter as tk
from tkinter import BOTH, HORIZONTAL, X, filedialog, messagebox
from typing import TYPE_CHECKING, Any, Optional

import requests
import ttkbootstrap as ttk

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.domain.services.library_scanner import LibraryScanner
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.data.remote.types import RemoteVersionDTO
    from sd_cpp_gui.infrastructure.i18n import I18nManager
    from sd_cpp_gui.plugins.core_remote.window import RemoteBrowserWindow

i18n: I18nManager = get_i18n()


class HashLookupTab(ttk.Frame):
    def __init__(
        self, parent: tk.Widget, controller: RemoteBrowserWindow
    ) -> None:
        """Logic: Initializes tab variables and builds UI."""
        super().__init__(parent)
        self.controller = controller
        self.current_hash_file: Optional[str] = None
        self.current_hash_meta: Optional[RemoteVersionDTO] = None
        self.var_rescan_all = tk.BooleanVar(value=False)
        self.scanner: Optional[LibraryScanner] = None
        self._init_ui()

    def _download_preview(self, url: str, dest_path: str) -> None:
        """Logic: Downloads an image from URL with API auth
        headers if needed."""
        try:
            if os.path.exists(dest_path):
                return
            headers = {}
            api_key = self.controller.settings.get("civitai_api_key", "")
            if api_key and "civitai.com" in url:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = requests.get(url, headers=headers, stream=True, timeout=10)
            if resp.status_code == 200:
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(1024):
                        f.write(chunk)
        except Exception:
            pass

    def destroy(self) -> None:
        """Logic: Stops any active scanner and destroys widget."""
        if self.scanner:
            self.scanner.stop()
        super().destroy()

    def _init_ui(self) -> None:
        """Logic: Builds UI sections: Single File Lookup and
        Bulk Library Scanner."""
        box = ttk.Frame(self, padding=20)
        box.pack(fill=BOTH, expand=True)
        lbl_info = CopyLabel(
            box,
            text=i18n.get(
                "remote.hash.lbl_info",
                "Identify a single file to check for updates"
                " or download metadata.",
            ),
            font=(SYSTEM_FONT, 12),
            wraplength=500,
        )
        lbl_info.pack(pady=10)
        self.lbl_hash_res = CopyLabel(
            box,
            text=i18n.get("remote.hash.lbl_no_file", "No file selected"),
            bootstyle="info",
            font=(SYSTEM_FONT, 10, "bold"),
            wraplength=600,
        )
        self.lbl_hash_res.pack(pady=10)
        flat.RoundedButton(
            box,
            text=i18n.get("remote.hash.btn_select", "Select File"),
            command=self._start_hash_calc,
            width=200,
            bootstyle="primary",
            corner_radius=CORNER_RADIUS,
        ).pack(pady=10)
        self.btn_hash_sync = flat.RoundedButton(
            box,
            text=i18n.get("remote.hash.btn_sync", "Sync Metadata to DB"),
            command=self._sync_hash_metadata,
            state="disabled",
            width=200,
            bootstyle="success",
            corner_radius=CORNER_RADIUS,
        )
        self.btn_hash_sync.pack(pady=10)
        ttk.Separator(box, orient=HORIZONTAL).pack(fill=X, pady=20)
        bulk_frame = ttk.Labelframe(
            box,
            text=i18n.get("remote.hash.grp_library", "Library Sync"),
            padding=15,
            bootstyle="primary",
        )
        bulk_frame.pack(fill=X, pady=10)
        CopyLabel(
            bulk_frame,
            text=i18n.get(
                "remote.hash.lbl_library_info",
                "Scan your entire library (Checkpoints,"
                " LoRAs, Embeddings) to fetch metadata "
                "from Civitai based on file hashes.",
            ),
            wraplength=600,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Checkbutton(
            bulk_frame,
            text=i18n.get(
                "remote.hash.chk_rescan",
                "Re-scan items that already have metadata",
            ),
            variable=self.var_rescan_all,
        ).pack(anchor="w", pady=(0, 10))
        self.btn_bulk_scan = flat.RoundedButton(
            bulk_frame,
            text=i18n.get("remote.hash.btn_scan_library", "Start Library Scan"),
            command=self._start_bulk_scan,
            width=200,
            bootstyle="warning",
            corner_radius=CORNER_RADIUS,
        )
        self.btn_bulk_scan.pack(anchor="w")
        self.lbl_bulk_status = CopyLabel(
            bulk_frame,
            text=i18n.get("remote.hash.status_idle", "Idle"),
            font=(SYSTEM_FONT, 9),
        )
        self.lbl_bulk_status.pack(anchor="w", pady=(10, 0))
        self.pb_bulk = ttk.Progressbar(bulk_frame, bootstyle="success-striped")
        self.pb_bulk.pack(fill=X, pady=(5, 0))

    def _start_bulk_scan(self) -> None:
        """Logic: Initiates the LibraryScanner in a background thread."""
        self.btn_bulk_scan.configure(state="disabled")
        self.scanner = LibraryScanner(
            self.controller.managers,
            self.controller.remote,
            progress_cb=self._update_bulk_progress,
            status_cb=self._update_bulk_status,
            finish_cb=self._on_bulk_finish,
        )
        self.scanner.start(scan_all=self.var_rescan_all.get())

    def _update_bulk_progress(self, val: float) -> None:
        """Logic: Updates bulk scan progress bar on main thread."""
        self.after(0, lambda: self.pb_bulk.configure(value=val))

    def _update_bulk_status(self, txt: str) -> None:
        """Logic: Updates bulk scan status label on main thread."""
        self.after(0, lambda: self.lbl_bulk_status.configure(text=txt))

    def _on_bulk_finish(self, success_count: int, total: int) -> None:
        """Logic: Schedules bulk scan finalization on main thread."""
        self.after(0, lambda: self._finalize_bulk(success_count, total))

    def _finalize_bulk(self, success: int, total: int) -> None:
        """Logic: Resets UI state and shows completion message for bulk scan."""
        self.btn_bulk_scan.configure(state="normal")
        self.controller.ownership.refresh()

        title = i18n.get("remote.hash.msg.scan_complete", "Scan Complete")
        msg = i18n.get(
            "remote.hash.msg.scan_results",
            "Processed {total} files.\nSuccessfully updated {success} items.",
        ).format(total=total, success=success)
        messagebox.showinfo(title, msg, parent=self)
        self.lbl_bulk_status.configure(text=f"Done. Updated {success}/{total}.")

    def _start_hash_calc(self) -> None:
        """Logic: Opens file dialog and starts hash calculation thread
        for single file."""
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[
                (
                    i18n.get("editor.filetype.models", "Models"),
                    "*.safetensors *.ckpt *.pt *.gguf",
                )
            ],
        )
        if not path:
            return
        self.current_hash_file = path
        self.current_hash_meta = None
        self.btn_hash_sync.configure(state="disabled")

        status = i18n.get(
            "remote.hash.status_calc", "Calculating SHA256 for {filename}..."
        ).format(filename=os.path.basename(path))
        self.lbl_hash_res.configure(text=status, bootstyle="warning")

        threading.Thread(
            target=self._calc_hash_thread, args=(path,), daemon=True
        ).start()

    def _calc_hash_thread(self, path: str) -> None:
        """Logic: Calculates SHA256 hash of file and triggers lookup."""
        sha256 = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1048576), b""):
                    sha256.update(chunk)
            digest = sha256.hexdigest().upper()
            self.after(0, lambda: self._lookup_hash(digest, path))
        except Exception as e:
            self.after(
                0,
                lambda e=e: self.lbl_hash_res.configure(
                    text=f"Error reading file: {e}", bootstyle="danger"
                ),
            )

    def _lookup_hash(self, digest: str, path: str) -> None:
        """Logic: Fetches metadata by hash, saves sidecars (json/preview),
        and updates UI."""
        self.lbl_hash_res.configure(
            text=f"Hash: {digest}\nSearching Civitai...", bootstyle="info"
        )

        def task() -> None:
            try:
                res = self.controller.remote.fetch_rich_metadata(
                    hash_value=digest
                )
                if res:
                    self.controller.remote.sidecar.save_metadata(path, res)
                    if "_parent_model" in res:
                        self.controller.remote.sidecar.save_metadata(
                            path, res["_parent_model"], suffix=".model"
                        )  # type: ignore
                    if res.get("images"):
                        img_url = res["images"][0].get("url")
                        if img_url:
                            self.controller.remote.sidecar.download_preview(
                                path, img_url
                            )
                self.after(0, lambda: self._on_hash_found(res, digest))
            except Exception as e:
                self.after(
                    0,
                    lambda e=e: self.lbl_hash_res.configure(
                        text=f"Search failed: {e}", bootstyle="danger"
                    ),
                )

        threading.Thread(target=task, daemon=True).start()

    def _on_hash_found(self, res: Any, digest: str) -> None:
        """Logic: Updates UI with found metadata or shows not found message."""
        if res:
            self.current_hash_meta = res
            txt = (
                f"✅ Found: {res['name']} (Base: {res['base_model']})\n"
                f"ID: {res['id']}"
            )
            self.lbl_hash_res.configure(text=txt, bootstyle="success")
            self.btn_hash_sync.configure(state="normal")
        else:
            self.lbl_hash_res.configure(
                text=f"No match found for hash {digest}", bootstyle="danger"
            )

    def _sync_hash_metadata(self) -> None:
        """Logic: Triggers registration of found metadata into DB."""
        if not self.current_hash_file or not self.current_hash_meta:
            return
        self._sync_with_type_inference()

    def _sync_with_type_inference(self) -> None:
        """Logic: Fetches parent model details to infer type
        before registering."""
        if not self.current_hash_meta:
            return
        mid = self.current_hash_meta["model_id"]

        def task() -> None:
            try:
                repo = self.controller.remote.get_repository("civitai")
                model_dto = repo.get_model_details(str(mid))
                if model_dto:
                    self.after(
                        0, lambda: self._finalize_sync(model_dto["type"])
                    )
            except Exception as e:
                print(e)

        threading.Thread(target=task, daemon=True).start()

    def _finalize_sync(self, model_type: str) -> None:
        """Logic: Registers model in appropriate manager and
        shows success message."""
        mgr = self.controller.get_manager_by_type(model_type)
        if self.current_hash_file and self.current_hash_meta:
            mgr.register_from_remote(
                self.current_hash_file, self.current_hash_meta
            )
        self.controller.ownership.refresh()
        messagebox.showinfo(
            "Sync Complete",
            f"File registered as {model_type} with rich metadata!",
        )
        self.btn_hash_sync.configure(state="disabled")
