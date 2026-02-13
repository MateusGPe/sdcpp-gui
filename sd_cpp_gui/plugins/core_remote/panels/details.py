"""
Updated DetailsPanel with file existence checks and auto-renaming logic.
"""

from __future__ import annotations

import html
import os
import threading
import tkinter as tk
from tkinter import BOTH, END, LEFT, X, filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, Optional

import ttkbootstrap as ttk

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.domain.utils.sanitization import (
    get_unique_filename,
    make_filename_portable,
)
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.plugins.core_remote.components.image_gallery import ImageGallery
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.data.remote.types import RemoteModelDTO, RemoteVersionDTO
    from sd_cpp_gui.infrastructure.i18n import I18nManager
    from sd_cpp_gui.plugins.core_remote.window import (
        RemoteBrowserWindow,
    )

i18n: I18nManager = get_i18n()


class DetailsPanel(ttk.Frame):
    def __init__(
        self, parent: tk.Widget, controller: RemoteBrowserWindow
    ) -> None:
        """Logic: Initializes panel and builds UI layout."""
        super().__init__(parent)
        self.controller = controller
        self.current_model_data: Optional[RemoteModelDTO] = None
        self.current_version_data: Optional[RemoteVersionDTO] = None
        self.version_map: Dict[str, Any] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        """Logic: Constructs UI sections: Header, Gallery,
        Version/Download Actions, Info Grid, Triggers, and Description."""
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill=X, pady=(0, 5))
        self.lbl_det_title = CopyLabel(
            self.header_frame,
            text=i18n.get("remote.details.lbl_select", "Select a model"),
            font=(SYSTEM_FONT, 14, "bold"),
            wraplength=300,
            bootstyle="primary",
        )
        self.lbl_det_title.pack(anchor="w")
        self.lbl_det_creator = CopyLabel(
            self.header_frame,
            text="",
            font=(SYSTEM_FONT, 9, "italic"),
            bootstyle="secondary",
        )
        self.lbl_det_creator.pack(anchor="w")
        self.gallery = ImageGallery(self, self.controller.img_loader)
        self.gallery.pack(fill=X, pady=5)
        action_frame = ttk.Frame(self)
        action_frame.pack(fill=X, pady=5)
        v_row = ttk.Frame(action_frame)
        v_row.pack(fill=X, pady=(0, 5))
        CopyLabel(
            v_row,
            text=i18n.get("remote.details.lbl_ver", "Version:"),
            font=(SYSTEM_FONT, 9, "bold"),
        ).pack(side=LEFT, padx=(0, 5))
        self.cb_versions = ttk.Combobox(
            v_row, state="readonly", font=(SYSTEM_FONT, 9)
        )
        self.cb_versions.pack(side=LEFT, fill=X, expand=True)
        self.cb_versions.bind("<<ComboboxSelected>>", self._on_version_selected)
        self.btn_download = flat.RoundedButton(
            action_frame,
            text=i18n.get("remote.details.btn_download", "Download"),
            state="disabled",
            command=self._download_selected,
            bootstyle="success",
            corner_radius=CORNER_RADIUS,
            height=35,
        )
        self.btn_download.pack(fill=X)
        self.info_frame = ttk.Frame(self, padding=5)
        self.info_frame.pack(fill=X, pady=5)

        lbl_base = i18n.get("remote.details.lbl_base", "Base: {base}").format(
            base="-"
        )
        self.lbl_info_base = CopyLabel(
            self.info_frame, text=lbl_base, font=(SYSTEM_FONT, 9)
        )
        self.lbl_info_base.grid(row=0, column=0, sticky="w", padx=(0, 10))

        lbl_size = i18n.get("remote.details.lbl_size", "Size: {size}").format(
            size="-"
        )
        self.lbl_info_size = CopyLabel(
            self.info_frame, text=lbl_size, font=(SYSTEM_FONT, 9)
        )
        self.lbl_info_size.grid(row=0, column=1, sticky="w", padx=(0, 10))

        lbl_date = i18n.get("remote.details.lbl_date", "Date: {date}").format(
            date="-"
        )
        self.lbl_info_date = CopyLabel(
            self.info_frame, text=lbl_date, font=(SYSTEM_FONT, 9)
        )
        self.lbl_info_date.grid(row=0, column=2, sticky="w")
        self.trigger_frame = ttk.Frame(self)
        desc_frame = ttk.Labelframe(
            self,
            text=i18n.get("remote.details.grp_desc", "Description"),
            padding=5,
        )
        desc_frame.pack(fill=BOTH, expand=True, pady=5)
        style = ttk.Style()
        bg = style.colors.bg
        if "secondary" in self.winfo_parent() and hasattr(
            style.colors, "secondary"
        ):
            bg = style.colors.secondary
        self.txt_desc = ttk.Text(
            desc_frame,
            height=5,
            width=30,
            font=(SYSTEM_FONT, 9),
            wrap="word",
            bd=0,
            bg=bg,
            relief="flat",
        )
        self.txt_desc.pack(fill=BOTH, expand=True)

    def load_model(self, dto: RemoteModelDTO) -> None:
        """Entry point for SearchTab to load data.

        Logic: Updates UI with model basic info, fetches full
        details in background."""
        self.current_model_data = dto
        self.lbl_det_title.configure(text=dto["name"])

        creator_txt = i18n.get("remote.details.lbl_by", "By: {creator}").format(
            creator=dto["creator"]
        )
        self.lbl_det_creator.configure(text=creator_txt)

        self.lbl_info_base.configure(
            text=i18n.get("remote.details.lbl_base", "Base: {base}").format(
                base="..."
            )
        )
        self.lbl_info_size.configure(
            text=i18n.get("remote.details.lbl_size", "Size: {size}").format(
                size="-"
            )
        )

        self.txt_desc.delete("1.0", END)
        self.txt_desc.insert("1.0", i18n.get("status.loading", "Loading..."))
        self.trigger_frame.pack_forget()
        self.version_map = {v["name"]: v["id"] for v in dto["versions"]}
        self.cb_versions["values"] = list(self.version_map.keys())
        if self.version_map:
            self.cb_versions.current(0)
        self._fetch_full_details(dto["id"])

    def _fetch_full_details(self, model_id: Any) -> None:
        """Logic: Fetches detailed model data from repo in background."""

        def task() -> None:
            try:
                repo = self.controller.remote.get_repository(
                    self.controller.current_provider
                )
                full = repo.get_model_details(str(model_id))
                if full:
                    self.after(0, lambda: self._update_full_model_data(full))
            except Exception as e:
                print(f"Details error: {e}")

        threading.Thread(target=task, daemon=True).start()

    def _update_full_model_data(self, dto: RemoteModelDTO) -> None:
        """Called when full details are loaded.

        Logic: Updates internal data, repopulates version combo,
        and selects first version."""
        self.current_model_data = dto
        self.version_map = {v["name"]: v["id"] for v in dto.get("versions", [])}
        values = list(self.version_map.keys())
        self.cb_versions["values"] = values
        if values:
            self.cb_versions.current(0)
            self._on_version_selected(None)

    def _on_version_selected(self, _e: Any) -> None:
        """Logic: Checks local ownership, updates Download button state,
        and triggers version detail fetch."""
        vid = self.version_map.get(self.cb_versions.get())
        if not vid or not self.current_model_data:
            return
        m_type = self.current_model_data.get("type", "Checkpoint")
        if self.controller.ownership.check_version(m_type, vid):
            self.btn_download.configure(
                text=i18n.get("remote.details.btn_installed", "✅ Installed"),
                state="disabled",
                bootstyle="secondary",
            )
        else:
            self.btn_download.configure(
                text=i18n.get("remote.details.btn_download", "Download"),
                state="normal",
                bootstyle="success",
            )

        def task() -> None:
            repo = self.controller.remote.get_repository(
                self.controller.current_provider
            )
            v_dto = repo.get_version_details(str(vid))
            self.after(0, lambda: self._render_version_data(v_dto))

        threading.Thread(target=task, daemon=True).start()

    def _render_version_data(self, v_dto: Optional[RemoteVersionDTO]) -> None:
        """Logic: Updates UI (Gallery, Stats, Triggers, Description)
        with version specific data."""
        if not v_dto:
            return
        self.current_version_data = v_dto
        self.gallery.load_images(v_dto["images"])
        base = v_dto.get("base_model", "Unknown")
        date = v_dto.get("published_at", "")[:10]
        size_str = "Unknown"
        if v_dto.get("files"):
            kb = v_dto["files"][0].get("size_kb", 0)
            size_str = (
                f"{kb / 1024:.2f} MB"
                if kb < 1024 * 1024
                else f"{kb / (1024 * 1024):.2f} GB"
            )
        self.lbl_info_base.configure(
            text=i18n.get("remote.details.lbl_base", "Base: {base}").format(
                base=base
            )
        )
        self.lbl_info_size.configure(
            text=i18n.get("remote.details.lbl_size", "Size: {size}").format(
                size=size_str
            )
        )
        self.lbl_info_date.configure(
            text=i18n.get("remote.details.lbl_date", "Date: {date}").format(
                date=date
            )
        )
        triggers = v_dto.get("trigger_words", [])
        for w in self.trigger_frame.winfo_children():
            w.destroy()
        if triggers:
            self.trigger_frame.pack(fill=X, pady=5, after=self.info_frame)
            f_trig = ttk.Frame(self.trigger_frame)
            f_trig.pack(fill=X)
            for t in triggers[:8]:
                btn = ttk.Button(
                    f_trig, text=t, bootstyle="info-outline", cursor="hand2"
                )
                btn.pack(side=LEFT, padx=1, pady=1)
                btn.configure(command=lambda x=t: self._copy_trigger(x))
        else:
            self.trigger_frame.pack_forget()
        desc = ""
        if "description" in v_dto and v_dto["description"]:
            desc = (
                html.unescape(v_dto["description"])
                .replace("<p>", "")
                .replace("</p>", "\n")
                .replace("<br>", "\n")
            )
        self.txt_desc.delete("1.0", END)
        self.txt_desc.insert("1.0", desc)

    def _copy_trigger(self, text: str) -> None:
        """Logic: Copies trigger word to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(text)

        status_msg = i18n.get(
            "remote.details.status_copied", "Copied '{text}'"
        ).format(text=text)
        self.controller.status_bar.configure(text=status_msg, bootstyle="info")

    def _download_selected(self) -> None:
        """Logic: Orchestrates download: determines path/filename,
        sanitizes name, checks existence, and starts download via controller."""
        if not self.current_version_data or not self.current_model_data:
            return
        self.btn_download.configure(state="disabled")
        url = self.current_version_data["download_url"]
        m_type = self.current_model_data.get("type", "checkpoint").lower()
        model_name = make_filename_portable(self.current_model_data["name"])
        version_name = make_filename_portable(self.current_version_data["name"])
        original_fname = "model.safetensors"
        for f in self.current_version_data.get("files", []):
            if f["download_url"] == url:
                original_fname = f["name"]
                break
        ext = os.path.splitext(original_fname)[1]
        fname = f"{model_name}_{version_name}{ext}"
        target_dir = ""
        is_manual = False
        if "checkpoint" in m_type:
            base = self.controller.settings.get("path_checkpoint")
            if base:
                target_dir = os.path.join(base, model_name)
            else:
                is_manual = True
        elif "lora" in m_type:
            target_dir = self.controller.settings.get("path_lora")
            if not target_dir:
                is_manual = True
        elif "embedding" in m_type:
            target_dir = self.controller.settings.get("path_embedding")
            if not target_dir:
                is_manual = True
        else:
            is_manual = True
        if is_manual:
            target_dir = filedialog.askdirectory(
                parent=self, title=f"Select folder for {m_type}"
            )
        if not target_dir:
            self.btn_download.configure(state="normal")
            return
        os.makedirs(target_dir, exist_ok=True)
        fname = get_unique_filename(target_dir, fname)
        preview_url = None
        if self.current_version_data.get("images"):
            preview_url = self.current_version_data["images"][0]["url"]
        try:
            meta = self.current_version_data.copy()
            meta["type"] = m_type
            self.controller.remote.download_with_metadata(
                url=url,
                dest_folder=target_dir,
                filename=fname,
                metadata=meta,
                preview_url=preview_url,
            )
            self.controller.notebook.select(self.controller.tab_downloads)
            self.controller.status_bar.configure(
                text=f"Downloading {fname}", bootstyle="info"
            )
        except Exception as e:
            messagebox.showerror(
                i18n.get("status.error", "Error"), str(e), parent=self
            )
            self.btn_download.configure(state="normal")
