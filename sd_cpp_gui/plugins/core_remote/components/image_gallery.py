from __future__ import annotations

from tkinter import BOTH, LEFT, RIGHT
from typing import TYPE_CHECKING, Any, List

import ttkbootstrap as ttk

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    import tkinter as tk

    from sd_cpp_gui.domain.services.image_loader import ImageLoader
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class ImageGallery(ttk.Frame):
    def __init__(self, parent: tk.Widget, img_loader: ImageLoader) -> None:
        """
        Logic: Initializes gallery with image display
        area and navigation buttons."""
        super().__init__(parent)
        self.img_loader = img_loader
        self.images: List[Any] = []
        self.current_idx = 0
        self.btn_prev = flat.RoundedButton(
            self, text="<", width=30, command=self.prev, bootstyle="secondary"
        )
        self.btn_prev.pack(side=LEFT, padx=5)

        no_img_text = i18n.get("remote.gallery.no_images", "No Images")
        self.lbl_img = CopyLabel(
            self, text=no_img_text, anchor="center", font=(SYSTEM_FONT, 10)
        )
        self.lbl_img.pack(side=LEFT, fill=BOTH, expand=True)
        self.btn_next = flat.RoundedButton(
            self, text=">", width=30, command=self.next, bootstyle="secondary"
        )
        self.btn_next.pack(side=RIGHT, padx=5)

    def load_images(self, urls: List[Any]) -> None:
        """Logic: Sets image list and resets index to 0."""
        self.images = urls
        self.current_idx = 0
        self.update_view()

    def update_view(self) -> None:
        """Logic: Requests the current image from loader and updates
        display or shows placeholder."""
        if not self.images:
            self.lbl_img.configure(
                image="", text=i18n.get("remote.gallery.no_images", "No Images")
            )
            return
        url = self.images[self.current_idx]
        if isinstance(url, dict):
            url = url.get("url")

        self.lbl_img.configure(text=i18n.get("status.loading", "Loading..."))
        if url:
            self.img_loader.request(url, self._on_img_loaded, size=(350, 350))

    def _on_img_loaded(self, tk_img: Any) -> None:
        """Logic: Callback to render the loaded image."""
        if self.winfo_exists():
            self.lbl_img.configure(image=tk_img, text="")
            self.lbl_img.image = tk_img  # type: ignore

    def next(self) -> None:
        """Logic: Advances to next image cyclically."""
        if self.images:
            self.current_idx = (self.current_idx + 1) % len(self.images)
            self.update_view()

    def prev(self) -> None:
        """Logic: Moves to previous image cyclically."""
        if self.images:
            self.current_idx = (self.current_idx - 1) % len(self.images)
            self.update_view()
