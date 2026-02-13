"""
ConfigTab - Enhanced Layout
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import BOTH, RIGHT, E, W, X, filedialog, messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import entry, flat
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.i18n import I18nManager
    from sd_cpp_gui.plugins.core_remote.window import (
        RemoteBrowserWindow,
    )

i18n: I18nManager = get_i18n()


class ConfigTab(ttk.Frame):
    def __init__(
        self, parent: tk.Widget, controller: RemoteBrowserWindow
    ) -> None:
        """Logic: Initializes config variables with current
        settings and builds UI."""
        super().__init__(parent)
        self.controller = controller
        self.var_civitai_key = tk.StringVar(
            value=self.controller.settings.get("civitai_api_key", "")
        )
        self.var_hf_key = tk.StringVar(
            value=self.controller.settings.get("hf_api_token", "")
        )
        self.var_path_ckpt = tk.StringVar(
            value=self.controller.settings.get("path_checkpoint", "")
        )
        self.var_path_lora = tk.StringVar(
            value=self.controller.settings.get("path_lora", "")
        )
        self.var_path_embed = tk.StringVar(
            value=self.controller.settings.get("path_embedding", "")
        )
        self._init_ui()

    def _init_ui(self) -> None:
        """Logic: Builds layout: Header, Auth section,
        Storage section, and Save button."""
        main_container = ttk.Frame(self, padding=20)
        main_container.pack(fill=BOTH, expand=True)
        CopyLabel(
            main_container,
            text=i18n.get(
                "remote.config.title", "Settings & API Configuration"
            ),
            font=(SYSTEM_FONT, 16, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=(0, 20))
        self._build_auth_section(main_container)
        self._build_storage_section(main_container)
        footer = ttk.Frame(main_container)
        footer.pack(fill=X, pady=5)
        flat.RoundedButton(
            footer,
            text=i18n.get("remote.config.btn_save", "💾 Save Configuration"),
            command=self._save_config,
            width=200,
            height=45,
            bootstyle="success",
            corner_radius=CORNER_RADIUS,
            font=(SYSTEM_FONT, 11, "bold"),
        ).pack(side=RIGHT)

    def _build_auth_section(self, parent: ttk.Frame) -> None:
        """Builds the API Key section using a grid layout.

        Logic: Creates inputs for Civitai and HuggingFace
        tokens with help links."""
        group = ttk.Labelframe(
            parent,
            text=i18n.get("remote.config.grp_auth", " 🔑 Authentication "),
            padding=15,
            bootstyle="info",
        )
        group.pack(fill=X, pady=(0, 10))
        group.columnconfigure(1, weight=1)
        CopyLabel(
            group,
            text=i18n.get("remote.config.lbl_civitai", "Civitai API Key:"),
            font=(SYSTEM_FONT, 10, "bold"),
        ).grid(row=0, column=0, sticky=W, padx=(0, 10), pady=5)
        entry.MEntry(
            group,
            textvariable=self.var_civitai_key,
            password_mode=True,
            bootstyle="info",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=5)
        flat.RoundedButton(
            group,
            text=i18n.get("remote.config.btn_get_key", "Get Key ↗"),
            command=lambda: webbrowser.open(  # type: ignore
                "https://civitai.com/user/settings"
            ),
            width=100,
            bootstyle="info-outline",
            corner_radius=CORNER_RADIUS,
        ).grid(row=0, column=2, sticky=E, pady=5)
        CopyLabel(
            group,
            text=i18n.get(
                "remote.config.lbl_civitai_note",
                "Required for NSFW content and higher rate limits.",
            ),
            font=(SYSTEM_FONT, 8),
            bootstyle="secondary",
        ).grid(row=1, column=1, sticky=W, pady=(0, 15))
        ttk.Separator(group, orient="horizontal").grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=10
        )
        CopyLabel(
            group,
            text=i18n.get("remote.config.lbl_hf", "HuggingFace Token:"),
            font=(SYSTEM_FONT, 10, "bold"),
        ).grid(row=3, column=0, sticky=W, padx=(0, 10), pady=5)
        entry.MEntry(
            group,
            textvariable=self.var_hf_key,
            password_mode=True,
            bootstyle="warning",
        ).grid(row=3, column=1, sticky="ew", padx=(0, 10), pady=5)
        flat.RoundedButton(
            group,
            text=i18n.get("remote.config.btn_get_token", "Get Token ↗"),
            command=lambda: webbrowser.open(  # type: ignore
                "https://huggingface.co/settings/tokens"
            ),
            width=100,
            bootstyle="warning-outline",
            corner_radius=CORNER_RADIUS,
        ).grid(row=3, column=2, sticky=E, pady=5)

    def _build_storage_section(self, parent: ttk.Frame) -> None:
        """Builds the Path selection section using a grid layout.

        Logic: Creates rows for Checkpoint, LoRA, and Embedding
        path selection."""
        group = ttk.Labelframe(
            parent,
            text=i18n.get(
                "remote.config.grp_storage", " 📂 Download Locations "
            ),
            padding=15,
            bootstyle="primary",
        )
        group.pack(fill=X, pady=(0, 10))
        group.columnconfigure(1, weight=1)

        def add_path_row(
            row_idx, label_key, default_label, var, color="primary"
        ):
            CopyLabel(
                group,
                text=i18n.get(label_key, default_label),
                font=(SYSTEM_FONT, 9),
            ).grid(row=row_idx, column=0, sticky=W, padx=(0, 10), pady=8)
            e = entry.MEntry(
                group, textvariable=var, state="readonly", bootstyle=color
            )
            e.grid(row=row_idx, column=1, sticky="ew", padx=(0, 10), pady=8)
            flat.RoundedButton(
                group,
                text=i18n.get("remote.config.btn_browse", "📂 Browse"),
                width=100,
                bootstyle=f"{color}",
                corner_radius=CORNER_RADIUS,
                command=lambda: self._browse_folder(var),
            ).grid(row=row_idx, column=2, sticky=E, pady=8)

        add_path_row(
            0,
            "remote.config.lbl_ckpt",
            "Checkpoints:",
            self.var_path_ckpt,
            "primary",
        )
        add_path_row(
            1, "remote.config.lbl_lora", "LoRAs:", self.var_path_lora, "success"
        )
        add_path_row(
            2,
            "remote.config.lbl_embed",
            "Embeddings:",
            self.var_path_embed,
            "info",
        )
        CopyLabel(
            group,
            text=i18n.get(
                "remote.config.lbl_storage_note",
                "ℹ Note: Checkpoints are automatically saved into"
                " subfolders named after the model.",
            ),
            font=(SYSTEM_FONT, 9, "italic"),
            bootstyle="secondary",
        ).grid(row=3, column=0, columnspan=3, sticky=W, pady=(10, 0))

    def _browse_folder(self, var: tk.StringVar) -> None:
        """Logic: Opens folder browser and updates the variable."""
        path = filedialog.askdirectory(parent=self)
        if path:
            var.set(path)

    def _save_config(self) -> None:
        """Saves API keys and refreshes remote manager.

        Logic: Persists settings, clears remote cache,
        re-checks API key status, and shows confirmation."""
        civitai_key = self.var_civitai_key.get().strip()
        hf_key = self.var_hf_key.get().strip()
        self.controller.settings.set("civitai_api_key", civitai_key)
        self.controller.settings.set("hf_api_token", hf_key)
        self.controller.settings.set(
            "path_checkpoint", self.var_path_ckpt.get().strip()
        )
        self.controller.settings.set(
            "path_lora", self.var_path_lora.get().strip()
        )
        self.controller.settings.set(
            "path_embedding", self.var_path_embed.get().strip()
        )
        self.controller.remote.clear_cache()
        self.controller.check_api_key()
        messagebox.showinfo(
            i18n.get("remote.config.msg.saved_title", "Configuration Saved"),
            i18n.get(
                "remote.config.msg.saved_desc",
                "Settings have been saved successfully.",
            ),
            parent=self,
        )
