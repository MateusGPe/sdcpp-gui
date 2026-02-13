from pathlib import Path
from typing import Any, Dict, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import LEFT
from ttkbootstrap.widgets import ToolTip

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.core.db.models import NetworkData
from sd_cpp_gui.core.i18n import get_i18n
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.controls.numeric_control import NumericControl

i18n = get_i18n()


class LoraWidget(NumericControl):
    """Widget for a single LoRA, using a standard NumericControl base."""

    def __init__(self, parent, data: NetworkData, on_change=None):
        self.data = data
        self.on_change = on_change
        name_txt = data.get("alias", i18n.get("common.unknown"))
        triggers = data.get("trigger_words", "")
        tooltip_txt = f"{i18n.get('lora.col.filename')}: {data.get('filename')}"
        if triggers:
            tooltip_txt += f"\n{i18n.get('lora.col.triggers')}: {triggers}"

        self._wrap_job = None

        super().__init__(
            parent,
            name=name_txt,
            arg_type="Float",
            flag="--lora",
            description=tooltip_txt,
            default_val=data.get("preferred_strength", 1.0),
        )
        self.var_enabled.set(False)
        self.toggle_state()

    def _build_ui(self):
        # Build the standard NumericControl UI first
        super()._build_ui()

        # --- Customizations for LoRA widget ---

        # 1. Configure layout weights and font for the name label
        self.columnconfigure(1, weight=1)
        self.lbl_name.grid_configure(sticky="ew")
        self.lbl_name.configure(font=(SYSTEM_FONT, 9))

        # 2. Make label wraplength dynamic
        def update_wraplength(_event):
            if self._wrap_job:
                self.after_cancel(self._wrap_job)
            if self.lbl_name.winfo_exists():

                def _wrap_later():
                    if self.lbl_name.winfo_exists():
                        self.lbl_name.config(wraplength=self.lbl_name.winfo_width())

                self._wrap_job = self.after(100, _wrap_later)

        self.lbl_name.bind("<Configure>", update_wraplength)

        # 3. Adjust the slider's range and behavior
        self.slider.configure(from_=-2.0, to=2.0)
        self.lbl_name.bind(
            "<Double-1>",
            lambda e: self.var_value.set(self.data.get("preferred_strength", 1.0)),
            add="+",
        )

        if self.on_change:
            self.var_value.trace_add("write", self._notify_change)
            self.var_enabled.trace_add("write", self._notify_change)

    def update_remote(self, enabled, value):
        if isinstance(value, tuple) and len(value) >= 1:
            strength = value[0]
            if self.var_value.get() != strength:
                self.var_value.set(strength)

        if self.var_enabled.get() != enabled:
            self.var_enabled.set(enabled)
            self.toggle_state()

    def _notify_change(self, *_args):
        if self.on_change:
            self.on_change(
                self.var_enabled.get(),
                "lora",
                self.data.get("name", self.name),
                (self.var_value.get(), self.data["dir_path"]),
            )

    @property
    def var_active(self):
        return self.var_enabled

    def get_data_if_active(self) -> Optional[Dict[str, Any]]:
        if self.var_enabled.get():
            return {
                "dir": self.data["dir_path"],
                "alias": self.data.get("alias"),
                "filename": self.data["filename"],
                "name": Path(self.data["path"]).stem,
                "strength": self.var_value.get(),
                "triggers": self.data.get("trigger_words"),
            }
        return None

    def reset(self):
        """Resets the widget to its default state."""
        self.set_value(self.default_val)
        if self.var_enabled.get():
            self.var_enabled.set(False)
            self.toggle_state()


class EmbeddingWidget(NumericControl):
    """
    Widget for a single Embedding.
    Uses sign of strength to determine Positive/Negative prompt target.
    """

    def __init__(self, parent, data: NetworkData, on_change=None):
        self.data = data
        self.on_change = on_change

        name_txt = data.get("alias", data.get("name", i18n.get("common.unknown")))
        triggers = data.get("trigger_words", "")
        tooltip_txt = (
            f"{i18n.get('lora.col.filename')}: {data.get('filename')}\n"
            f"{i18n.get('lora.col.triggers')}: {triggers if triggers else name_txt}"
        )

        super().__init__(
            parent,
            name=name_txt,
            arg_type="Float",
            flag="--embd-dir",
            description=tooltip_txt,
            default_val=1.0,
        )

        self.var_enabled.set(False)
        self.toggle_state()

    def _build_ui(self):
        super()._build_ui()

        # Configure Label
        self.columnconfigure(1, weight=1)
        self.lbl_name.grid_configure(sticky="ew")
        self.lbl_name.configure(font=(SYSTEM_FONT, 9))

        def update_wraplength(_event):
            if self.lbl_name.winfo_exists():
                self.lbl_name.config(wraplength=self.lbl_name.winfo_width())

        self.lbl_name.bind("<Configure>", update_wraplength)

        # Configure Slider
        self.slider.configure(from_=-2.0, to=2.0)

        # Reset on double click
        self.lbl_name.bind(
            "<Double-1>",
            lambda e: self.var_value.set(1.0),
            add="+",
        )

        if self.on_change:
            self.var_value.trace_add("write", self._notify_change)
            self.var_enabled.trace_add("write", self._notify_change)

    def _notify_change(self, *_args):
        if self.on_change:
            val = self.var_value.get()
            target = "positive" if val >= 0 else "negative"
            self.on_change(
                self.var_enabled.get(),
                "embedding",
                self.data.get("name", self.name),
                (target, abs(val), self.data["dir_path"]),
            )

    def update_remote(self, enabled, value):
        target = "positive"
        strength = 1.0

        if isinstance(value, (tuple, list)):
            if len(value) >= 1:
                target = value[0]
            if len(value) >= 2:
                strength = float(value[1])
            if len(value) >= 3:
                self.data["dir_path"] = value[2]
        elif isinstance(value, str):
            target = value if value in ["positive", "negative"] else "positive"

        signed_val = strength if target == "positive" else -strength

        if self.var_value.get() != signed_val:
            self.var_value.set(signed_val)

        if self.var_enabled.get() != enabled:
            self.var_enabled.set(enabled)
            self.toggle_state()

    def get_data_if_active(self) -> Optional[Dict[str, Any]]:
        if self.var_enabled.get():
            val = self.var_value.get()
            target = "positive" if val >= 0 else "negative"
            # If no trigger words are defined, use the alias/name as the trigger
            trigger = self.data.get("trigger_words") or self.data.get("name")

            return {
                "dir": self.data["dir_path"],
                "trigger": trigger,
                "target": target,  # "positive" or "negative"
                "strength": abs(val),
            }
        return None

    def reset(self):
        """Resets the widget to its default 'none' state."""
        self.set_value(1.0)
        if self.var_enabled.get():
            self.var_enabled.set(False)
            self.toggle_state()

    def get_status(self):
        return {
            "arg_type": "string",
            "flag": "--embd-dir",  # Dummy flag for grouping
            "name": self.name,
        }
