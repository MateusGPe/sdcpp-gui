from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import ttkbootstrap as ttk

from sd_cpp_gui.constants import EMOJI_FONT, SYSTEM_FONT
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    import tkinter as tk

    from sd_cpp_gui.data.remote.types import RemoteModelDTO
    from sd_cpp_gui.domain.services.image_loader import ImageLoader
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class ModelCard(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        dto: RemoteModelDTO,
        on_click: Callable[[RemoteModelDTO], None],
        img_loader: ImageLoader,
        owned_versions: int = 0,
    ) -> None:
        """Logic: Creates a card widget displaying model image (async load),
        title, stats, type, and owned status."""
        style = "secondary" if owned_versions == 0 else "success"
        super().__init__(parent, bootstyle=style, padding=5)
        self.dto = dto
        self.on_click = on_click
        self.img_loader = img_loader
        self.columnconfigure(0, weight=1)
        self.lbl_img = CopyLabel(
            self, text="📷", anchor="center", font=(EMOJI_FONT, 24)
        )
        self.lbl_img.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        if dto["image_url"]:
            self.img_loader.request(
                dto["image_url"], self.update_image, size=(180, 240)
            )
        title = dto["name"]
        if len(title) > 22:
            title = title[:20] + "..."
        CopyLabel(
            self, text=title, font=(SYSTEM_FONT, 9, "bold"), anchor="w"
        ).grid(row=1, column=0, sticky="ew")
        stats = (
            f"⭐ {dto.get('rating', 0.0):.1f} | "
            f"⬇ {self._format_number(dto.get('download_count', 0))}"
        )
        CopyLabel(
            self, text=stats, font=(SYSTEM_FONT, 8), bootstyle="secondary"
        ).grid(row=2, column=0, sticky="ew")
        type_txt = dto["type"]
        if owned_versions > 0:
            type_txt += i18n.get("remote.card.owned", " (Owned)")
        CopyLabel(
            self,
            text=type_txt,
            font=(SYSTEM_FONT, 8, "bold"),
            bootstyle="info" if owned_versions == 0 else "success",
        ).grid(row=3, column=0, sticky="w")
        for w in self.winfo_children():
            w.bind("<Button-1>", lambda e: self.on_click(self.dto))
        self.bind("<Button-1>", lambda e: self.on_click(self.dto))

    def _format_number(self, num: int) -> str:
        """Logic: Formats large numbers into human-readable strings (k, M)."""
        if num >= 1e6:
            return f"{num / 1e6:.1f}M"
        if num >= 1e3:
            return f"{num / 1e3:.1f}k"
        return str(num)

    def update_image(self, tk_img: Any) -> None:
        """Logic: Callback to update the image label once loaded."""
        if self.winfo_exists():
            self.lbl_img.configure(image=tk_img, text="")
            self.lbl_img.image = tk_img  # type: ignore
