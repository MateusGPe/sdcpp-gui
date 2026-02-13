from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional, cast

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import BOTH, X

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    import tkinter as tk

    from sd_cpp_gui.domain.generation import StateManager
    from sd_cpp_gui.infrastructure.i18n import I18nManager
    from sd_cpp_gui.ui.controls.numeric_control import NumericControl
    from sd_cpp_gui.ui.controls.path_control import PathControl

i18n: I18nManager = get_i18n()


class Img2ImgSection(ttk.Frame):
    """Img2Img Section."""

    def __init__(self, parent: tk.Widget, state_manager: StateManager) -> None:
        """Logic: Initializes Img2Img Section."""
        super().__init__(parent)
        self.state_manager = state_manager
        self.path_control: PathControl
        self.strength_control: NumericControl
        self.lbl_thumb: Optional[CopyLabel] = None
        self._init_ui()

    @property
    def var_init_img(self) -> tk.StringVar:
        """Logic: Returns image path var."""
        return cast(tk.StringVar, self.path_control.var_value)

    @property
    def var_strength(self) -> tk.DoubleVar:
        """Logic: Returns strength var."""
        return cast(tk.DoubleVar, self.strength_control.var_value)

    def _init_ui(self) -> None:
        """Logic: Builds UI."""
        CopyLabel(
            self,
            text=i18n.get("img2img.title"),
            font=(SYSTEM_FONT, 12, "bold"),
            bootstyle="primary",
        ).pack(fill=X, pady=(0, 10))
        f_main = ttk.Frame(self)
        f_main.pack(fill=BOTH, expand=True)
        f_main.columnconfigure(0, weight=1)
        f_main.rowconfigure(2, weight=1)
        self.path_control = self.state_manager.new_argument_control(
            f_main, "--init-img"
        )
        self.path_control.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.path_control.var_value.trace_add("write", self._on_path_change)
        self.strength_control = self.state_manager.new_argument_control(
            f_main, "--strength"
        )
        self.strength_control.grid(row=1, column=0, sticky="ew")
        self.strength_control.slider.configure(from_=0.0, to=1.0)
        self.strength_control._center_slider_range = lambda: None
        if self.strength_control:
            for w in self.strength_control.winfo_children():
                if isinstance(w, flat.RoundedButton):
                    w.destroy()
                    break
        self.lbl_thumb = CopyLabel(
            f_main,
            text=i18n.get("img2img.no_img"),
            anchor="center",
            bootstyle="secondary-inverse",
        )
        self.lbl_thumb.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self._on_path_change()

    def reset(self) -> None:
        """Resets the Img2Img controls to their default state.

        Logic: Resets controls."""
        self.strength_control.set_value(self.strength_control.default_val)
        self.path_control.set_value("")

    def _on_path_change(self, *_args: Any) -> None:
        """Logic: Handles path change."""
        path = self.path_control.var_value.get()
        is_valid_path = path and os.path.exists(str(path))
        if is_valid_path:
            if not self.strength_control.var_enabled.get():
                self.strength_control.var_enabled.set(True)
                self.strength_control.toggle_state()
            self.update_thumb(str(path))
        else:
            if self.strength_control.var_enabled.get():
                self.strength_control.var_enabled.set(False)
                self.strength_control.toggle_state()
            self.clear_thumb()

    def clear_img(self) -> None:
        """Logic: Clears image path."""
        self.path_control.set_value("")

    def clear_thumb(self) -> None:
        """Logic: Clears thumbnail."""
        if self.lbl_thumb and self.lbl_thumb.winfo_exists():
            self.lbl_thumb.configure(image="", text=i18n.get("img2img.no_img"))
            self.lbl_thumb.image = None  # type: ignore

    def update_thumb(self, path: str) -> None:
        """Logic: Updates thumbnail."""
        if not self.lbl_thumb or not self.lbl_thumb.winfo_exists():
            return
        try:
            with Image.open(path) as img:
                img.thumbnail((384, 384))
                tk_img = ImageTk.PhotoImage(img)
            self.lbl_thumb.configure(image=tk_img, text="")
            self.lbl_thumb.image = tk_img  # type: ignore
        except Exception:
            self.clear_thumb()
