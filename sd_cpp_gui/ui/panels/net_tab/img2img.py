import os
from typing import Optional

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import BOTH, X

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.core.i18n import get_i18n
from sd_cpp_gui.ui.argument_manager import ArgumentManager
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.controls.numeric_control import NumericControl
from sd_cpp_gui.ui.components.controls.path_control import PathControl

i18n = get_i18n()


class Img2ImgSection(ttk.Frame):
    """Img2Img Section."""

    def __init__(self, parent, arg_manager: ArgumentManager):
        super().__init__(parent)
        self.arg_manager = arg_manager
        self.path_control: PathControl
        self.strength_control: NumericControl
        self.lbl_thumb: Optional[ttk.Label] = None
        self._init_ui()

    @property
    def var_init_img(self):
        return self.path_control.var_value

    @property
    def var_strength(self):
        return self.strength_control.var_value

    def _init_ui(self):
        ttk.Label(
            self,
            text=i18n.get("img2img.title"),
            font=(SYSTEM_FONT, 12, "bold"),
            bootstyle="primary",
        ).pack(fill=X, pady=(0, 10))

        f_main = ttk.Frame(self)
        f_main.pack(fill=BOTH, expand=True)
        f_main.columnconfigure(0, weight=1)
        f_main.rowconfigure(2, weight=1)

        # --- Path Control for Init Image ---
        self.path_control = self.arg_manager.new_argument_control(
            f_main,
            "--init-img",
        )
        self.path_control.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.path_control.var_value.trace_add("write", self._on_path_change)

        # --- Strength Control ---
        self.strength_control = self.arg_manager.new_argument_control(
            f_main,
            "--strength",
        )
        self.strength_control.grid(row=1, column=0, sticky="ew")

        # Customize strength control for 0-1 range
        self.strength_control.slider.configure(from_=0.0, to=1.0)
        # Disable auto-ranging by overriding the method and removing the button
        self.strength_control._center_slider_range = lambda: None
        for w in self.strength_control.input_container.winfo_children():
            if isinstance(w, flat.RoundedButton):
                w.destroy()
                break

        # --- Thumbnail Preview ---
        self.lbl_thumb = ttk.Label(
            f_main,
            text=i18n.get("img2img.no_img"),
            anchor="center",
            bootstyle="secondary-inverse",
        )
        self.lbl_thumb.grid(row=2, column=0, sticky="nsew", pady=(10, 0))

        # --- Initial State ---
        self._on_path_change()

    def reset(self):
        """Resets the Img2Img controls to their default state."""
        self.strength_control.set_value(self.strength_control.default_val)
        self.path_control.set_value("")  # This will trigger the disabling

    def _on_path_change(self, *_args):
        path = self.path_control.var_value.get()
        is_valid_path = path and os.path.exists(path)

        # Enable/disable strength control based on path
        if is_valid_path:
            if not self.strength_control.var_enabled.get():
                self.strength_control.var_enabled.set(True)
                self.strength_control.toggle_state()
            self.update_thumb(path)
        else:
            if self.strength_control.var_enabled.get():
                self.strength_control.var_enabled.set(False)
                self.strength_control.toggle_state()
            self.clear_thumb()

    def clear_img(self):
        self.path_control.set_value("")

    def clear_thumb(self):
        if self.lbl_thumb and self.lbl_thumb.winfo_exists():
            self.lbl_thumb.configure(image="", text=i18n.get("img2img.no_img"))
            self.lbl_thumb.image = None

    def update_thumb(self, path):
        if not self.lbl_thumb or not self.lbl_thumb.winfo_exists():
            return
        try:
            img = Image.open(path)
            img.thumbnail((384, 384))
            tk_img = ImageTk.PhotoImage(img)
            self.lbl_thumb.configure(image=tk_img, text="")
            self.lbl_thumb.image = tk_img
        except Exception:
            self.clear_thumb()
