from __future__ import annotations

import os
import platform
import subprocess
import tkinter as tk
from tkinter import filedialog
from typing import Any, Optional

import ttkbootstrap as ttk
from PIL import Image, ImageTk

from sd_cpp_gui.constants import CORNER_RADIUS
from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components.flat import RoundedButton
from sd_cpp_gui.ui.components.utils import CopyLabel

logger = get_logger(__name__)

i18n: I18nManager = get_i18n()


class ImageViewer(ttk.Frame):
    """Handles the display and resizing of the generated image."""

    def __init__(self, parent: Any, background: str, **kwargs: Any) -> None:
        """Logic: Initializes image viewer."""
        super().__init__(parent, bootstyle=background, **kwargs)
        self.side_color = background
        self.current_image: Optional[Image.Image] = None
        self.current_path: Optional[str] = None
        self._image_tk: Optional[ImageTk.PhotoImage] = None
        self._resize_timer: Optional[str] = None
        self._hq_timer: Optional[str] = None
        self._is_hq_image = False

        # Zoom and Pan state
        self.zoom_mode = "fit"
        self.scale = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._drag_data = {"x": 0, "y": 0}

        self.style = ttk.Style.get_instance()

        self.f_toolbar = ttk.Frame(self, bootstyle="dark", padding=2)
        self.f_toolbar.pack(fill=tk.X, side=tk.TOP)

        self.btn_folder = RoundedButton(
            self.f_toolbar,
            text="📂",
            bootstyle="dark",
            command=self._open_folder,
            width=28,
            height=28,
            corner_radius=CORNER_RADIUS,
            elevation=1,
        )
        self.btn_folder.pack(side=tk.LEFT)

        self.btn_save = RoundedButton(
            self.f_toolbar,
            text="💾",
            bootstyle="dark",
            command=self._save_as,
            width=28,
            height=28,
            corner_radius=CORNER_RADIUS,
            elevation=1,
        )
        self.btn_save.pack(side=tk.LEFT)

        self.btn_reset = RoundedButton(
            self.f_toolbar,
            text="⟲",
            bootstyle="dark",
            command=self._reset_view,
            width=28,
            height=28,
            corner_radius=CORNER_RADIUS,
            elevation=1,
        )
        self.btn_reset.pack(side=tk.LEFT)

        self.lbl_filename = CopyLabel(
            self.f_toolbar,
            text="",
            bootstyle="inverse-dark",
            anchor="center",
        )
        self.lbl_filename.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_zoom_in = RoundedButton(
            self.f_toolbar,
            text="➕",
            bootstyle="dark",
            command=self._zoom_in,
            width=26,
            height=26,
            corner_radius=10,
            elevation=1,
        )
        self.btn_zoom_in.pack(side=tk.RIGHT)

        self.lbl_zoom = ttk.Label(
            self.f_toolbar,
            text="100%",
            bootstyle="inverse-dark",
            width=6,
            anchor="center",
        )
        self.lbl_zoom.pack(side=tk.RIGHT)
        self.btn_zoom_out = RoundedButton(
            self.f_toolbar,
            text="➖",
            bootstyle="dark",
            command=self._zoom_out,
            width=26,
            height=26,
            corner_radius=10,
            elevation=1,
        )
        self.btn_zoom_out.pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(
            self,
            bd=0,
            highlightthickness=0,
            bg=self._get_bg_color(),
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", self._on_resize_event)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)
        self.canvas.bind("<Double-Button-1>", self._reset_view)

        self._create_context_menu()
        trigger = (
            "<Button-2>" if platform.system() == "Darwin" else "<Button-3>"
        )
        self.canvas.bind(trigger, self._show_context_menu)

        self.after_idle(self.update_theme)
        self.after(200, self._draw_placeholder)

    def _get_bg_color(self, attr="dark") -> str:
        try:
            return getattr(self.style.colors, attr)
        except AttributeError:
            return "#1e1e1e"

    def _create_context_menu(self) -> None:
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="Open Folder", command=self._open_folder
        )
        self.context_menu.add_command(label="Save As...", command=self._save_as)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Reset View", command=self._reset_view
        )

    def _show_context_menu(self, event: tk.Event) -> None:
        if self.current_image:
            self.context_menu.tk_popup(event.x_root + 1, event.y_root + 1)

    def _open_folder(self) -> None:
        if not self.current_path:
            return
        folder = os.path.dirname(self.current_path)
        if not os.path.exists(folder):
            return
        try:
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    def _save_as(self) -> None:
        if not self.current_image:
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("JPEG Image", "*.jpg"),
                ("All Files", "*.*"),
            ],
        )
        if file_path:
            try:
                self.current_image.save(file_path)
            except Exception as e:
                logger.error(f"Failed to save image: {e}")

    def _reset_view(self, _event: Any = None) -> None:
        self.zoom_mode = "fit"
        self._update_image_display(force_hq=True)

    def _zoom_in(self) -> None:
        self._perform_zoom(1.1)

    def _zoom_out(self) -> None:
        self._perform_zoom(0.9)

    def _perform_zoom(self, factor: float) -> None:
        if not self.current_image:
            return
        if self.zoom_mode == "fit":
            self.zoom_mode = "manual"

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        mx = self.canvas.canvasx(w / 2)
        my = self.canvas.canvasy(h / 2)
        vx = mx - self.pan_x
        vy = my - self.pan_y
        self.scale *= factor
        self.pan_x = mx - (vx * factor)
        self.pan_y = my - (vy * factor)
        self._update_image_display(force_hq=False)
        self._trigger_hq_update()

    def update_theme(self, side_color: str = "dark") -> None:
        """Logic: Updates theme."""
        self.side_color = side_color
        self.configure(bootstyle=side_color)
        self.canvas.configure(bg=self._get_bg_color(side_color))
        if not self.current_image:
            self._draw_placeholder()

    def show_image(self, path: str) -> None:
        """Logic: Shows image."""
        self.current_path = path
        self.after(0, lambda: self._show_image_impl(path))

    def _show_image_impl(self, path: str, retries: int = 0) -> None:
        """Logic: Implementation of show image."""
        if not path:
            return
        if not os.path.exists(path):
            if retries < 100:
                self.after(
                    100, lambda: self._show_image_impl(path, retries + 1)
                )
            return
        try:
            with Image.open(path) as img:
                self.current_image = img.copy()
            self.current_image.load()
            self._image_tk = None
            self.lbl_filename.configure(text=os.path.basename(path))
            self.zoom_mode = "fit"
            self._update_image_display(force_hq=True)
        except Exception as e:
            logger.error(f"Error loading image {path}: {e}")

    def _draw_placeholder(self) -> None:
        self.canvas.delete("all")
        fg = "white"
        self.canvas.create_text(
            self.winfo_width() // 2,
            self.winfo_height() // 2,
            text=i18n.get("preview.none"),
            fill=fg,
            anchor="center",
            tags="placeholder",
        )

    def _on_resize_event(self, _event: Any) -> None:
        """Logic: Handles resize."""
        if self._resize_timer:
            self.after_cancel(self._resize_timer)
        self._resize_timer = self.after(
            300, lambda: self._update_image_display(force_hq=False)
        )
        self._trigger_hq_update()

    def _trigger_hq_update(self) -> None:
        if self._hq_timer:
            self.after_cancel(self._hq_timer)
        self._hq_timer = self.after(
            800, lambda: self._update_image_display(force_hq=True)
        )

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self.current_image:
            return
        if self.zoom_mode == "fit":
            self.zoom_mode = "manual"
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self.pan_x += dx
        self.pan_y += dy
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._update_image_display(force_hq=False)
        self._trigger_hq_update()

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        if not self.current_image:
            return
        if event.num == 5 or event.delta < 0:
            factor = 0.9
        else:
            factor = 1.1
        if self.zoom_mode == "fit":
            self.zoom_mode = "manual"
        mx = self.canvas.canvasx(event.x)
        my = self.canvas.canvasy(event.y)
        vx = mx - self.pan_x
        vy = my - self.pan_y
        self.scale *= factor
        self.pan_x = mx - (vx * factor)
        self.pan_y = my - (vy * factor)
        self._update_image_display(force_hq=False)
        self._trigger_hq_update()

    def _update_image_display(self, force_hq: bool = True) -> None:
        """Logic: Updates image display."""
        self._resize_timer = None
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if not self.current_image:
            self._draw_placeholder()
            return

        if w < 10 or h < 10:
            return

        img_w, img_h = self.current_image.size

        if self.zoom_mode == "fit":
            ratio = min(w / img_w, h / img_h)
            self.scale = ratio
            self.pan_x = w / 2
            self.pan_y = h / 2
        if self.scale < 0.1:
            self.scale = 0.1

        new_w = int(img_w * self.scale)
        new_h = int(img_h * self.scale)
        if new_w > 4096 or new_h > 4096:
            self.scale = min(4096 / img_w, 4096 / img_h)
            new_w = int(img_w * self.scale)
            new_h = int(img_h * self.scale)

        self.lbl_zoom.configure(text=f"{int(self.scale * 100)}%")
        if new_w < 1 or new_h < 1:
            return

        if new_w < w:
            self.pan_x = w / 2
        else:
            min_x = w - new_w / 2
            max_x = new_w / 2
            if self.pan_x < min_x:
                self.pan_x = min_x
            elif self.pan_x > max_x:
                self.pan_x = max_x

        if new_h < h:
            self.pan_y = h / 2
        else:
            min_y = h - new_h / 2
            max_y = new_h / 2
            if self.pan_y < min_y:
                self.pan_y = min_y
            elif self.pan_y > max_y:
                self.pan_y = max_y

        reuse_image = (
            self._image_tk
            and self._image_tk.width() == new_w
            and self._image_tk.height() == new_h
        )

        if reuse_image and force_hq and not self._is_hq_image:
            reuse_image = False

        if not reuse_image:
            resample_mode = (
                Image.Resampling.BICUBIC
                if force_hq
                else Image.Resampling.NEAREST
            )
            try:
                self._image_tk = ImageTk.PhotoImage(
                    self.current_image.resize((new_w, new_h), resample_mode)
                )
                self._is_hq_image = force_hq
                self.canvas.delete("all")
                self.canvas.create_image(
                    self.pan_x,
                    self.pan_y,
                    image=self._image_tk,
                    anchor="center",
                    tags="img",
                )
            except Exception as e:
                logger.warning(
                    i18n.get("preview.resize_error").format(e=e), "ERROR"
                )
        else:
            if self.canvas.find_withtag("img"):
                self.canvas.coords("img", self.pan_x, self.pan_y)
            else:
                self.canvas.create_image(
                    self.pan_x,
                    self.pan_y,
                    image=self._image_tk,
                    anchor="center",
                    tags="img",
                )
