from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, X
from ttkbootstrap.publisher import Channel, Publisher

from sd_cpp_gui.constants import CORNER_RADIUS, EMOJI_FONT, SYSTEM_FONT
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.color_manager import ColorManager
from sd_cpp_gui.ui.components.utils import CopyLabel, restore_sash

from .console import LogConsole
from .image_viewer import ImageViewer
from .param_viewer import ParamViewer
from .prompt_visual_view import PromptVisualView

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class PreviewPanel(ttk.Panedwindow):
    """
    Right-side panel for displaying images, generation parameters, and logs.
    Orchestrates sub-components.
    """

    def __init__(
        self, parent: tk.Misc, container: DependencyContainer, **kwargs: Any
    ) -> None:
        """Logic: Initializes preview panel."""
        super().__init__(parent, orient=tk.VERTICAL, **kwargs)
        self.container = container
        self.style = ttk.Style.get_instance()
        self.color_manager = ColorManager(self, {})
        self._showing_image = False
        self.current_view: Optional[str] = None
        self.last_state: Dict[str, Any] = {}
        self._anim_job: Optional[str] = None
        self._update_side_color_var()
        self._init_ui()
        Publisher.subscribe(
            name=str(id(self)), func=self.on_theme_change, channel=Channel.STD
        )

    def _update_side_color_var(self) -> None:
        """Logic: Updates side color."""
        self.side_color = (
            "light" if self.style.theme.type == "light" else "dark"
        )

    def _init_ui(self) -> None:
        """Logic: Builds UI."""
        self.configure(bootstyle=self.side_color)
        self.f_main_content = ttk.Frame(
            self, bootstyle=self.side_color, border=1
        )
        self.add(self.f_main_content, weight=4)
        self.f_main_content.grid_columnconfigure(0, weight=1)
        self.f_main_content.grid_rowconfigure(0, minsize=40)
        self.f_main_content.grid_rowconfigure(1, weight=1, minsize=100)
        self.f_main_content.grid_rowconfigure(2, minsize=40)
        self.f_toolbar = ttk.Frame(
            self.f_main_content, padding=(5, 5), bootstyle="secondary"
        )
        self.f_toolbar.grid(row=0, column=0, sticky="ew")
        self.btn_view_params = flat.RoundedButton(
            self.f_toolbar,
            text="📝 Params",
            bootstyle="primary",
            command=self._show_params_view,
            font=(EMOJI_FONT, 9),
            height=32,
            width=80,
            corner_radius=CORNER_RADIUS,
            elevation=1,
        )
        self.btn_view_params.pack(side=LEFT)
        self.btn_view_visual = flat.RoundedButton(
            self.f_toolbar,
            text="🎨 Tags",
            bootstyle="secondary",
            command=self._show_visual_view,
            font=(EMOJI_FONT, 9),
            height=32,
            width=80,
            corner_radius=CORNER_RADIUS,
            elevation=1,
        )
        self.btn_view_visual.pack(side=LEFT)
        self.btn_view_image = flat.RoundedButton(
            self.f_toolbar,
            text="🖼️ Image",
            bootstyle="secondary",
            command=self._show_image_view,
            font=(EMOJI_FONT, 9),
            height=32,
            width=80,
            corner_radius=CORNER_RADIUS,
            elevation=1,
        )
        self.btn_view_image.pack(side=LEFT)
        self.f_preview = ttk.Frame(
            self.f_main_content, bootstyle=self.side_color
        )
        self.f_preview.grid(row=1, column=0, sticky="nsew")
        self.image_viewer = ImageViewer(self.f_preview, background="dark")
        self.param_viewer = ParamViewer(
            self.f_preview,
            self.container.cmd_loader,
            side_color=self.side_color,
        )
        ac_service = getattr(self.container, "autocomplete", None)
        self.prompt_visual_view = PromptVisualView(
            self.f_preview,
            color_manager=self.color_manager,
            state_manager=self.container.state_manager,
            autocomplete_service=ac_service,
            padding=10,
        )
        self.f_status = ttk.Frame(
            self.f_main_content, padding=5, bootstyle=self.side_color
        )
        self.f_status.grid(row=2, column=0, sticky="ew")
        self.lbl_status = CopyLabel(
            self.f_status,
            text=i18n.get("preview.ready"),
            font=(SYSTEM_FONT, 10, "bold"),
            bootstyle=f"inverse-{self.side_color}",
        )
        self.lbl_status.pack(side=LEFT)
        self.btn_close_status = flat.RoundedButton(
            self.f_status,
            text="x",
            bootstyle="danger",
            command=self.hide_status,
            font=(SYSTEM_FONT, 9),
            height=20,
            width=20,
            corner_radius=8,
            elevation=1,
        )
        self.btn_close_status.pack(side=RIGHT)
        self.prog_bar = ttk.Progressbar(
            self.f_status, bootstyle="success-striped", mode="determinate"
        )
        self.prog_bar.pack(side=RIGHT, fill=X, expand=True, padx=5)
        self.console = LogConsole(self)
        self.add(self.console, weight=1)
        self.after(
            100, lambda: restore_sash(self.container.settings, "preview", self)
        )
        self._restore_last_view()

    def sync_with_state(self, full_state: Dict[str, Any]) -> None:
        """Logic: Syncs with state."""
        self.last_state = full_state
        self.param_viewer.sync_with_state(full_state)

    def log(self, text: str, msg_type: str = "RAW") -> None:
        """Logic: Logs text."""
        self.console.log(text, msg_type)

    def clear_console(self) -> None:
        """Logic: Clears console."""
        self.console.clear()

    def set_status(self, text: str, style: str = "secondary") -> None:
        """Logic: Sets status."""
        self.after(0, lambda: self._set_status_impl(text, style))

    def _set_status_impl(self, text: str, style: str) -> None:
        """Logic: Implementation of set status."""
        self.f_status.grid()
        self.lbl_status.config(
            text=text, foreground=self.style.colors.get(style)
        )

    def set_progress(self, value: float) -> None:
        """Logic: Sets progress."""
        self.after(0, lambda: self._set_progress_impl(value))

    def _set_progress_impl(self, value: float) -> None:
        """Logic: Implementation of set progress."""
        self.f_status.grid()
        self.prog_bar.configure(value=value)

    def hide_status(self) -> None:
        """Logic: Hides status bar."""
        self.f_status.grid_remove()

    def show_image(self, path: str) -> None:
        """Logic: Shows image."""
        self.image_viewer.show_image(path)
        if not self._showing_image:
            self._animate_image_button()

    def _animate_image_button(self, count: int = 0) -> None:
        """Logic: Animates image button."""
        if self._anim_job:
            self.after_cancel(self._anim_job)
            self._anim_job = None

        if not self.winfo_exists():
            return
        if self.current_view == "image":
            self.btn_view_image.configure(bootstyle="primary")
            return

        style = "success" if count % 2 == 0 else "secondary"
        self.btn_view_image.configure(bootstyle=style)

        if count < 6:
            self._anim_job = self.after(
                200, lambda: self._animate_image_button(count + 1)
            )
        else:
            self.btn_view_image.configure(bootstyle="success")

    def _restore_last_view(self) -> None:
        """Logic: Restores the last active view from settings."""
        last_view = self.container.settings.get("preview_active_view", "params")
        if last_view == "image":
            self._show_image_view()
        elif last_view == "visual":
            self._show_visual_view()
        else:
            self._show_params_view()

    def _reset_view_buttons(self) -> None:
        if self.current_view == "visual":
            self.prompt_visual_view.on_hide()

        self.btn_view_image.configure(bootstyle="secondary")
        self.btn_view_params.configure(bootstyle="secondary")
        self.btn_view_visual.configure(bootstyle="secondary")
        self.image_viewer.pack_forget()
        self.param_viewer.pack_forget()
        self.prompt_visual_view.pack_forget()

    def _show_image_view(self) -> None:
        """Logic: Switches to image view."""
        if self.current_view == "image":
            return
        self.container.settings.set("preview_active_view", "image")
        self._reset_view_buttons()
        self.current_view = "image"
        self._showing_image = True
        self.image_viewer.pack(fill=BOTH, expand=True)
        self.btn_view_image.configure(bootstyle="primary")
        if self.image_viewer.current_image:
            self.image_viewer._update_image_display()

    def _show_params_view(self) -> None:
        """Logic: Switches to params view."""
        if self.current_view == "params":
            return
        self.container.settings.set("preview_active_view", "params")
        self._reset_view_buttons()
        self.current_view = "params"
        self._showing_image = False
        self.param_viewer.pack(fill=BOTH, expand=True)
        self.btn_view_params.configure(bootstyle="primary")
        self.param_viewer._display_current_params()

    def _show_visual_view(self) -> None:
        """Logic: Switches to visual prompt view."""
        if self.current_view == "visual":
            return
        self.container.settings.set("preview_active_view", "visual")
        self._reset_view_buttons()
        self.current_view = "visual"
        self._showing_image = False
        self.prompt_visual_view.pack(fill=BOTH, expand=True)
        self.btn_view_visual.configure(bootstyle="primary")
        self.prompt_visual_view.on_show()

    def on_theme_change(self, _note: Any = None) -> None:
        """Logic: Handles theme change."""
        if not self.winfo_exists():
            Publisher.unsubscribe(str(id(self)))
            return
        self._update_side_color_var()
        self.configure(bootstyle=self.side_color)
        self.f_main_content.configure(bootstyle=self.side_color)
        self.f_preview.configure(bootstyle=self.side_color)
        self.f_status.configure(bootstyle=self.side_color)
        self.lbl_status.configure(bootstyle=f"inverse-{self.side_color}")
        self.image_viewer.update_theme("dark")
        self.param_viewer.update_theme(self.side_color)
        self.prompt_visual_view.update_theme(self.side_color)
