from __future__ import annotations

import tkinter as tk
from tkinter import BOTH, LEFT, X
from typing import TYPE_CHECKING, Any, Dict

import ttkbootstrap as ttk

from sd_cpp_gui.ui.components.scroll_frame import SmoothScrollFrame
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.plugins.core_remote.window import (
        RemoteBrowserWindow,
    )


class DownloadsTab(ttk.Frame):
    def __init__(
        self, parent: tk.Widget, controller: RemoteBrowserWindow
    ) -> None:
        """Logic: Initializes tab and creates scrollable frame."""
        super().__init__(parent)
        self.controller = controller
        self.progress_bars: Dict[str, Dict[str, Any]] = {}
        self.dl_frame = SmoothScrollFrame(self)
        self.dl_frame.pack(fill=BOTH, expand=True)

    def update_progress(self, data: Dict[str, Any]) -> None:
        """Updates download progress UI.

        Logic: Creates or updates progress bars for active downloads."""
        url = data["url"]
        fname = data["filename"]
        if url not in self.progress_bars:
            container = ttk.Frame(
                self.dl_frame.content, padding=5, bootstyle="bg"
            )
            container.pack(fill=X, pady=2)
            CopyLabel(container, text=fname, width=30, anchor="w").pack(
                side=LEFT
            )
            pb = ttk.Progressbar(
                container, maximum=100, bootstyle="success-striped"
            )
            pb.pack(side=LEFT, fill=X, expand=True, padx=5)
            lbl = CopyLabel(container, text="0%", width=6, anchor="e")
            lbl.pack(side=LEFT)
            self.progress_bars[url] = {"pb": pb, "lbl": lbl, "frame": container}
        widgets = self.progress_bars[url]
        widgets["pb"]["value"] = data["percent"]
        widgets["lbl"].configure(text=f"{int(data['percent'])}%")
