"""
Consolidated Network Widgets.
"""

from __future__ import annotations

import os
import tkinter as tk
import webbrowser
from tkinter import CENTER, LEFT, RIGHT, X
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, cast

import ttkbootstrap as tb
from PIL import Image, ImageOps, ImageTk

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.data.db.models import NetworkData
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.entry import MEntry
from sd_cpp_gui.ui.controls.numeric_control import NumericControl

if TYPE_CHECKING:
    from sd_cpp_gui.data.db.models import NetworkData
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class GhostNetworkWidget(tb.Frame):
    """
    A placeholder widget for network items found in state (History)
    but missing from the local file system.
    """

    def __init__(
        self,
        parent: tk.Widget,
        name: str,
        on_remove: Callable[[], None],
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Logic: Initializes ghost widget UI with warning label
        and action buttons.
        """
        super().__init__(parent)
        self.name = name
        self.on_remove = on_remove
        self.data = data or {}
        self.configure(bootstyle="danger")
        inner = tb.Frame(self, bootstyle="danger", padding=5)
        inner.pack(fill=X, expand=True)
        tb.Label(
            inner,
            text="⚠️ File Missing",
            bootstyle="inverse-danger",
            font=(SYSTEM_FONT, 8, "bold"),
        ).pack(anchor="w")
        tb.Label(
            inner,
            text=f"{name}\n(strength {self.data.get('strength')})",
            bootstyle="inverse-danger",
            font=(SYSTEM_FONT, 9),
        ).pack(anchor="w", pady=(2, 0))
        btn_frame = tb.Frame(inner, bootstyle="danger")
        btn_frame.pack(fill=X, pady=(5, 0))
        if self.data.get("remote_version_id"):
            flat.RoundedButton(
                btn_frame,
                text="🌐 Civitai",
                width=80,
                height=24,
                corner_radius=CORNER_RADIUS,
                bootstyle="danger",
                command=self._open_remote,
            ).pack(side=LEFT)
        flat.RoundedButton(
            self,
            text="✕",
            width=32,
            height=32,
            corner_radius=CORNER_RADIUS,
            bootstyle="danger",
            command=self.on_remove,
        ).pack(side=RIGHT)

    def _open_remote(self) -> None:
        """Logic: Opens remote URL."""
        vid = self.data.get("remote_version_id")
        if vid:
            webbrowser.open(
                f"https://civitai.com/models/{vid}?modelVersionId={vid}"
            )

    def update_remote(self, enabled: bool, value: Any) -> None:
        """Pass-through to satisfy interface."""
        pass

    def get_data_if_active(self) -> Optional[Dict[str, Any]]:
        """Ghost items should never contribute to generation parameters."""
        return None

    def reset(self) -> None:
        """If reset is called, we remove this ghost item."""
        self.on_remove()


class BaseNetworkWidget(NumericControl):
    """
    Base class for LoRA and Embedding widgets with Enhanced UI (Thumbnails).
    """

    def __init__(
        self,
        parent: tk.Widget,
        data: NetworkData,
        on_change: Optional[Callable[[str, str, Any, bool], None]],
        on_remove: Optional[Callable[[], None]],
        arg_type: str = "float",
    ):
        """Logic: Initializes widget with data and listeners."""
        self.data = data
        self.on_change = on_change
        self.on_remove = on_remove
        self._thumb_img = None
        name = (
            data.get("alias") or data.get("name") or i18n.get("common.unknown")
        )
        triggers = data.get("trigger_words", "")
        tooltip = f"File: {data.get('filename')}\nTriggers: {triggers}"
        super().__init__(
            parent,
            name=name,
            arg_type=arg_type,
            flag="",
            description=tooltip,
            default_val=1.0,
        )
        self.var_enabled.set(False)
        self.toggle_state()
        if self.on_change:
            self.var_value.trace_add("write", self._notify_change)
            self.var_enabled.trace_add("write", self._notify_change)

    @property
    def except_ctrl(self) -> set[tk.Widget]:
        ctrls = super().except_ctrl
        if hasattr(self, "_btn_remove"):
            ctrls.add(self._btn_remove)
        return ctrls

    def _build_ui(self) -> None:
        """
        Overrides NumericControl._build_ui to create a Card layout
        with Thumbnail, Slider, and Controls.

        Logic: Builds custom card UI.
        """
        self._normalize_configuration()
        current_val = self._get_current_value_safe()
        self.current_range = self._calculate_initial_range(current_val)
        self.entry_var = tk.StringVar(value=str(current_val))
        self.input_job = None
        self.entry_var.trace_add("write", self._on_entry_change)
        self.var_value.trace_add("write", self._on_var_change)
        self.configure(padding=5, bootstyle="default")
        self.columnconfigure(2, weight=1)
        self.lbl_thumb = tb.Label(self, bootstyle="secondary")
        self.lbl_thumb.grid(
            row=0, column=0, rowspan=2, padx=(0, 10), pady=0, sticky="nsew"
        )
        self._load_thumbnail()
        self.chk = tb.Checkbutton(
            self,
            variable=self.var_enabled,
            command=self.toggle_state,
            bootstyle="round-toggle",
        )
        self.chk.grid(row=0, column=1, sticky="ws")
        self.lbl_name = tb.Label(
            self,
            text=self.name,
            font=(SYSTEM_FONT, 9, "bold"),
            bootstyle="primary",
        )
        self.lbl_name.grid(
            row=0, column=2, columnspan=2, padx=(0, 0), sticky="ews"
        )
        if self.description:
            from ttkbootstrap.widgets import ToolTip

            ToolTip(self.lbl_name, text=self.description, bootstyle="info")
        if self.on_remove:
            self._btn_remove = flat.RoundedButton(
                self,
                text="✕",
                width=24,
                height=24,
                corner_radius=CORNER_RADIUS,
                command=self.on_remove,
                bootstyle="danger",
                elevation=1,
            )
            self._btn_remove.grid(row=0, column=4, padx=0, sticky="ne")
        self.slider = tb.Scale(
            self,
            from_=self.current_range[0],
            to=self.current_range[1],
            bootstyle="info",
            command=self._on_slider_move,
        )
        self.slider.grid(
            row=1, column=1, columnspan=2, sticky="nsew", padx=(0, 5)
        )
        self.input_widget = MEntry(
            self,
            textvariable=self.entry_var,
            width=80,
            height=50,
            radius=CORNER_RADIUS,
            elevation=2,
            justify="center",
        )
        self.input_widget.bind("<Return>", self._on_entry_change)
        self.input_widget.grid(row=1, column=3, columnspan=2, sticky="ew")
        self._on_var_change()

    def _load_thumbnail(self) -> None:
        """Loads preview image from sidecar file.

        Logic: Loads thumbnail if available."""
        model_path = self.data.get("path", "")
        if not model_path:
            self._set_placeholder()
            return
        base_path = os.path.splitext(model_path)[0]
        preview_path = None
        for ext in [".preview.png", ".preview.jpg", ".png", ".jpg", ".webp"]:
            candidate = base_path + ext
            if os.path.exists(candidate):
                preview_path = candidate
                break
        if not preview_path:
            self._set_placeholder()
            return
        try:
            size = (40, 60)
            with Image.open(preview_path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
                self._thumb_img = ImageTk.PhotoImage(img)
                self.lbl_thumb.configure(image=self._thumb_img)
        except Exception:
            self._set_placeholder()

    def _set_placeholder(self) -> None:
        """Sets a generic placeholder if no image found.

        Logic: Sets placeholder icon."""
        self.lbl_thumb.configure(
            text="📷", font=(SYSTEM_FONT, 20), anchor=CENTER, width=3
        )

    def _notify_change(self, *_):
        raise NotImplementedError

    def update_remote(self, enabled: bool, value: Any):
        raise NotImplementedError

    def get_data_if_active(self) -> Optional[Dict[str, Any]]:
        """Logic: Returns active data."""
        if not self.var_enabled.get():
            return None
        return {
            "dir": self.data["dir_path"],
            "triggers": self.data.get("trigger_words"),
            "strength": abs(float(self.var_value.get())),
        }

    def reset(self) -> None:
        """Logic: Resets widget."""
        self.set_value(self.default_val)
        if self.var_enabled.get():
            self.var_enabled.set(False)
            self.toggle_state()


class LoraWidget(BaseNetworkWidget):
    def __init__(self, parent, data, on_change=None, on_remove=None):
        """Logic: Initializes Lora widget."""
        data["preferred_strength"] = data.get("preferred_strength", 1.0)
        super().__init__(parent, data, on_change, on_remove)
        self.default_val = data["preferred_strength"]
        self.set_value(self.default_val)

    def _notify_change(self, *_):
        """Logic: Notifies LoRA change."""
        if self.on_change:
            val = self.var_value.get()
            self.on_change(
                "lora",
                self.data.get("name", self.name),
                (
                    val,
                    self.data["dir_path"],
                    self.data.get("trigger_words"),
                    self.data.get("content_hash"),
                    self.data.get("remote_version_id"),
                ),
                self.var_enabled.get() and val != 0.0,
            )

    def update_remote(self, enabled: bool, value: Any):
        """Logic: Updates state from remote."""
        if (
            isinstance(value, tuple)
            and len(value) >= 1
            and (self.var_value.get() != value[0])
        ):
            cast(tk.DoubleVar, self.var_value).set(value[0])
        if self.var_enabled.get() != enabled:
            self.var_enabled.set(enabled)
            self.toggle_state()


class EmbeddingWidget(BaseNetworkWidget):
    def _notify_change(self, *_):
        """Logic: Notifies Embedding change."""
        if self.on_change:
            val = self.var_value.get()
            target = "positive" if val >= 0 else "negative"
            triggers = self.data.get("trigger_words") or self.data.get("name")
            self.on_change(
                "embedding",
                self.data.get("name", self.name),
                (
                    target,
                    abs(val),
                    self.data["dir_path"],
                    triggers,
                    self.data.get("content_hash"),
                    self.data.get("remote_version_id"),
                ),
                self.var_enabled.get() and val != 0.0,
            )

    def update_remote(self, enabled: bool, value: Any):
        """Logic: Updates state from remote."""
        strength = 1.0
        target = "positive"
        if isinstance(value, (tuple, list)):
            if len(value) >= 1:
                target = value[0]
            if len(value) >= 2:
                strength = float(value[1])
        signed_val = strength if target == "positive" else -strength
        if self.var_value.get() != signed_val:
            cast(tk.DoubleVar, self.var_value).set(signed_val)
        if self.var_enabled.get() != enabled:
            self.var_enabled.set(enabled)
            self.toggle_state()

    def get_data_if_active(self):
        """Logic: Returns data if active."""
        d = super().get_data_if_active()
        if d:
            d["target"] = (
                "positive" if self.var_value.get() >= 0 else "negative"
            )
            d["trigger"] = d.pop("triggers") or self.data.get("name")
        return d
