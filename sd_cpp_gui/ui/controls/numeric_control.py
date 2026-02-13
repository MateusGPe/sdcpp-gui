"""
Numeric (Integer/Float) Argument Control with Slider
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union, cast

import ttkbootstrap as tb
from ttkbootstrap.widgets import ToolTip

from sd_cpp_gui.constants import CORNER_RADIUS
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.entry import MEntry
from sd_cpp_gui.ui.controls.base import BaseArgumentControl

if TYPE_CHECKING:
    pass
logger = get_logger("NumericControl")


class NumericControl(BaseArgumentControl):
    """A control for numeric arguments (int/float)
    with a slider and text entry."""

    def _build_ui(self) -> None:
        """Builds the UI for a numeric input control.

        Logic: Builds common UI, sets up slider range, adds slider,
        entry, and range centering button."""
        self._build_common_ui()
        self.slider: tb.Scale
        self.entry_var: tk.StringVar
        self.input_job: Optional[str] = None
        self.current_range: Tuple[float, float]
        self.columnconfigure(2, weight=1, minsize=80)
        self.columnconfigure(1, minsize=50)
        self._normalize_configuration()
        current_val = self._get_current_value_safe()
        self.current_range = self._calculate_initial_range(current_val)
        self.slider = tb.Scale(
            self,
            from_=self.current_range[0],
            to=self.current_range[1],
            bootstyle="info",
            command=self._on_slider_move,
        )
        self.slider.grid(row=0, column=2, sticky="ew", padx=(0, 5))
        self.entry_var = tk.StringVar(value=str(current_val))
        self.entry_var.trace_add("write", self._on_entry_change)
        self.var_value.trace_add("write", self._on_var_change)
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
        self.input_widget.grid(row=0, column=3, sticky="e", padx=(0, 1))
        btn_center = flat.RoundedButton(
            self,
            text="⚖️",
            width=32,
            height=32,
            corner_radius=CORNER_RADIUS,
            bootstyle="primary",
            command=self._center_slider_range,
            elevation=1,
        )
        ToolTip(btn_center, text="Adjust scale (2x current value)")
        btn_center.grid(row=0, column=4, sticky="e")
        self._on_var_change()

    def _normalize_configuration(self) -> None:
        """Normalizes arg_type and default_val.

        Logic: Ensures arg_type is valid numeric type and default_val
        is typed correctly."""
        try:
            self.default_val = float(self.default_val)  # type: ignore
        except (ValueError, TypeError):
            self.default_val = 0
        if "int" in self.arg_type:
            self.default_val = int(self.default_val)  # type: ignore
        if self.arg_type not in ["int", "integer", "float"]:
            logger.warning(
                "NumericControl initialized with non-numeric arg_type '%s' "
                "for '%s'. Defaulting to 'float'.",
                self.arg_type,
                self.name,
            )
            self.arg_type = "float"

    def _get_current_value_safe(self) -> Union[float, int]:
        """Safely retrieves the current value based on default_val.

        Logic: Returns safe numeric value from default."""
        try:
            val = float(self.default_val)  # type: ignore
            if "int" in self.arg_type:
                return int(val)
            return val
        except (ValueError, TypeError):
            return 0

    def _calculate_initial_range(
        self, current_val: Union[float, int]
    ) -> Tuple[float, float]:
        """Calculates the initial slider range.

        Logic: Determines min/max range for slider based on current value."""
        if current_val != 0:
            limit = float(current_val * 2)
        else:
            limit = 100.0 if "int" in self.arg_type.lower() else 1.0
        if limit > 0:
            return (0.0, limit)
        else:
            return (limit, 0.0)

    def set_value(self, value: Any) -> None:
        """Extends base set_value to also handle slider centering.

        Logic: Sets value and recenters slider."""
        super().set_value(value)
        self._center_slider_range()

    def _on_entry_change(self, *_args: Any) -> None:
        """Updates the main variable when the text entry changes.

        Logic: Parses entry text and updates var_value if valid."""
        txt = self.entry_var.get().replace(",", ".")
        if not txt:
            return
        try:
            if "int" in self.arg_type.lower():
                new_val_int = int(float(txt))
                if self.var_value.get() != new_val_int:
                    cast(tk.IntVar, self.var_value).set(new_val_int)
            else:
                new_val_float = float(txt)
                if abs(float(self.var_value.get()) - new_val_float) > 1e-06:
                    cast(tk.DoubleVar, self.var_value).set(new_val_float)
        except ValueError as e:
            logger.debug(
                "Invalid entry ignored for '%s': %s (%s)", self.name, txt, e
            )

    def _on_var_change(self, *_args: Any) -> None:
        """Updates the entry text when the main variable
        changes (e.g., from slider).

        Logic: Syncs entry text and slider position with var_value."""
        try:
            val = self.var_value.get()
            new_val_str = str(val)
            current_entry = self.entry_var.get()
            update_entry = True
            try:
                if current_entry:
                    current_float = float(current_entry.replace(",", "."))
                    new_float = float(new_val_str)
                    if abs(current_float - new_float) < 1e-06:
                        update_entry = False
            except ValueError:
                pass
            if update_entry:
                self.entry_var.set(new_val_str)
            if self.slider.winfo_exists():
                current_slider = self.slider.get()
                target_val = float(val)
                if abs(current_slider - target_val) > 1e-05:
                    self.slider.set(target_val)
        except tk.TclError as e:
            logger.warning("TclError while updating variable: %s", e)

    def _on_slider_move(self, val: str) -> None:
        """Rounds the value to int if necessary when slider moves.

        Logic: Updates var_value from slider, rounding as needed,
        and debounces range expansion."""
        try:
            cval = float(val)
            if "int" in self.arg_type.lower():
                ival = int(round(cval))
                cast(tk.IntVar, self.var_value).set(ival)
            else:
                cast(tk.DoubleVar, self.var_value).set(round(cval, 3))
            if self.input_job:
                self.after_cancel(self.input_job)
            self.input_job = self.after(
                800, lambda: self._expand_slider_range(float(cval))
            )
        except ValueError:
            pass

    def _expand_slider_range(self, cval: float) -> None:
        """Expands the slider range if the current value exceeds it.

        Logic: Increases slider range if value hits the bounds."""
        min_val, max_val = self.current_range
        new_min, new_max = (min_val, max_val)
        changed = False
        if cval >= max_val:
            new_max = cval * 1.41 if cval != 0 else 10.0
            changed = True
        elif cval <= min_val:
            new_min = cval * 1.41 if cval != 0 else -10.0
            changed = True
        if changed:
            self.current_range = (new_min, new_max)
            self.slider.configure(from_=new_min, to=new_max)

    def _center_slider_range(self) -> None:
        """Adjusts the slider's min/max range based on the current value.

        Logic: Recalculates slider min/max around current value."""
        try:
            val_str = self.entry_var.get()
            try:
                val = float(val_str) if val_str else float(self.var_value.get())
            except ValueError:
                val = float(self.var_value.get())
            if val == 0:
                try:
                    base = float(self.default_val)  # type: ignore
                except (ValueError, TypeError):
                    base = 0.0
                limit = base * 2 if base != 0 else 100.0
                self.slider.configure(from_=-limit, to=limit)
                self.current_range = (-limit, limit)
            else:
                mn, mx = (0.0, val * 2) if val > 0 else (val * 2, 0.0)
                if "int" in self.arg_type:
                    mn = int(mn)
                    mx = int(mx)
                self.current_range = (float(mn), float(mx))
                self.slider.configure(from_=mn, to=mx)
            self.slider.set(val)
        except (ValueError, tk.TclError) as e:
            logger.error("Error centering slider: %s", e)
