"""
Base class for all argument controls.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import ttkbootstrap as tb
from ttkbootstrap.widgets import ToolTip

from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n
from sd_cpp_gui.infrastructure.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("BaseArgumentControl")

i18n: I18nManager = get_i18n()


class BaseArgumentControl(tb.Frame):
    """
    Abstract base class for creating UI controls for command-line arguments.
    Decoupled from the raw data structure; accepts explicit parameters.
    """

    # pylint: disable=too-many-ancestors, too-many-instance-attributes
    def __init__(
        self,
        parent: tk.Widget,
        name: str,
        flag: str,
        arg_type: str,
        description: str,
        default_val: Union[str, int, float, bool, list],
        is_required: bool = False,
        options: Optional[List[str]] = None,
        file_types: Optional[List[tuple[str, str]]] = None,
        open_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initializes the base argument control with metadata and UI."""
        super().__init__(parent, **kwargs)
        self.name = name
        self.flag = flag
        self.arg_type = arg_type.strip().lower()
        self.description = description

        self.default_val: Union[str, int, float, bool]
        if self.arg_type in {"int", "integer"}:
            if isinstance(default_val, list):
                self.default_val = 0
            else:
                try:
                    self.default_val = int(default_val)  # type: ignore
                except (ValueError, TypeError):
                    self.default_val = 0
        elif self.arg_type in {"float"}:
            if isinstance(default_val, list):
                self.default_val = 0.0
            else:
                try:
                    self.default_val = float(default_val)  # type: ignore
                except (ValueError, TypeError):
                    self.default_val = 0.0
        elif self.arg_type in {"bool", "boolean", "flag"}:
            self.default_val = bool(default_val)
        else:
            self.default_val = (
                str(default_val) if default_val is not None else ""
            )

        self.is_required = is_required
        self.options = options or []
        self.file_types = file_types
        self.open_mode = open_mode
        self.lbl_name: tb.Label
        self.chk: tb.Checkbutton
        self.input_widget: Any = None
        self.is_overridden = False
        self.var_enabled = tk.BooleanVar(value=self.is_required)
        self.var_value = self._get_variable_type()
        self._toggle_job: Optional[str] = None
        self.columnconfigure(2, weight=1)
        self._build_ui()
        self.toggle_state()

    def _build_ui(self) -> None:
        """Builds the specific UI for the control.
        Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _build_ui")

    def _get_variable_type(
        self,
    ) -> Union[tk.IntVar, tk.DoubleVar, tk.BooleanVar, tk.StringVar]:
        """Determines the appropriate tkinter variable
        type based on the argument type."""

        if self.arg_type in {"integer", "int"}:
            return tk.IntVar(
                value=int(self.default_val)  # type: ignore
                if self.default_val is not None
                else 0
            )

        if self.arg_type == "float":
            return tk.DoubleVar(
                value=(
                    float(self.default_val)  # type: ignore
                    if self.default_val is not None
                    else 0.0
                )
            )

        if self.arg_type in {"flag", "boolean", "bool"}:
            return tk.BooleanVar(value=bool(self.default_val))

        val = self.default_val if self.default_val is not None else ""
        return tk.StringVar(value=str(val))

    def set_value(self, value: Any) -> None:
        """Safely sets the value of the control's variable,
        converting types if necessary."""
        logger.debug("Setting value for '%s': %s", self.name, value)
        try:
            str_val = str(value)

            if isinstance(self.var_value, tk.BooleanVar):
                is_true = str_val.lower() in ("true", "1", "yes", "on")
                self.var_value.set(is_true)
            elif isinstance(self.var_value, tk.IntVar):
                if "." in str_val:
                    self.var_value.set(int(float(str_val)))
                else:
                    self.var_value.set(int(str_val) if str_val else 0)
            elif isinstance(self.var_value, tk.DoubleVar):
                self.var_value.set(float(str_val) if str_val else 0.0)
            else:
                self.var_value.set(str_val)

            if not self.is_required and not self.is_overridden:
                self.var_enabled.set(True)
            self.toggle_state()
        except (ValueError, TypeError) as e:
            logger.error(
                "Error setting value for '%s': %s. Error: %s",
                self.name,
                value,
                e,
            )

    def set_override_mode(self, active: bool) -> None:
        """Sets whether this control is being managed externally
        (e.g., by a preset)."""
        self.is_overridden = active
        suffix = i18n.get("common.no_preset", "(In preset)")

        if active:
            self.var_enabled.set(False)
            self.chk.configure(state="disabled")
            self.lbl_name.configure(bootstyle="secondary")

            if not self.lbl_name.cget("text").endswith(suffix):
                self.lbl_name.configure(text=f"{self.name} {suffix}")
        else:
            if self.is_required:
                self.var_enabled.set(True)
                self.chk.configure(state="disabled")
            else:
                self.chk.configure(state="normal")
            self.lbl_name.configure(bootstyle="default")
            self.lbl_name.configure(text=self.name)
        self.toggle_state()

    def toggle_state(self) -> None:
        """
        Schedules a visual state update (enabled/disabled) for the inputs.
        Uses debouncing to prevent race conditions.
        """

        if self._toggle_job:
            self.after_cancel(self._toggle_job)
        self._toggle_job = self.after(5, self._do_toggle_state)

    @property
    def except_ctrl(self) -> set[tk.Widget]:
        """
        Returns a set of widgets that should be excluded
        from bulk state updates.
        """
        ctrls = {self.chk}
        if self.input_widget and hasattr(self.input_widget, "m_entry_widget"):
            ctrls.add(self.input_widget.m_entry_widget)
        return ctrls

    def _do_toggle_state(self) -> None:
        """Executes the actual state update."""
        self._toggle_job = None
        state = (
            "disabled"
            if self.is_overridden
            else ("normal" if self.var_enabled.get() else "disabled")
        )

        if self.input_widget:
            self._safe_configure_widget(self.input_widget, state)

        for child in set(self.winfo_children()).difference(self.except_ctrl):
            self._safe_configure_widget(child, state)

    def _safe_configure_widget(self, widget: Any, state: str) -> None:
        """Safely configures a widget's state, handling special cases."""
        try:
            if hasattr(widget, "winfo_exists") and not widget.winfo_exists():
                return

            if isinstance(widget, tb.Combobox):
                widget.configure(
                    state="readonly" if state == "normal" else "disabled"
                )
            elif isinstance(widget, tk.OptionMenu):
                widget.configure(
                    state="normal" if state == "normal" else "disabled"
                )
            elif isinstance(widget, tk.Canvas) and hasattr(widget, "configure"):

                def _after_idle(w: tk.Canvas = widget, s: str = state) -> None:
                    self._configure_canvas_widget(w, s)

                self.after_idle(_after_idle)
            else:
                widget.configure(state=state)
        except (tk.TclError, AttributeError):
            pass

    def _configure_canvas_widget(self, widget: tk.Canvas, state: str) -> None:
        """Asynchronously configures Canvas-based
        widgets to prevent race conditions."""
        try:
            if widget.winfo_exists():
                widget.configure(state=state)  # type: ignore[call-overload]
        except (tk.TclError, AttributeError):
            pass

    def get_command_arg(self) -> Optional[tuple[str, Any]]:
        """Returns the command-line flag and value, or None if disabled."""

        if not self.var_enabled.get():
            return None
        return (self.flag, self.var_value.get())

    def get_status(self) -> Dict[str, Any]:
        """Returns the current status and value of the control."""
        return {
            "enabled": self.var_enabled.get(),
            "value": self.var_value.get(),
            "name": self.name,
            "flag": self.flag,
            "arg_type": self.arg_type,
            "description": self.description,
            "default_val": self.default_val,
            "is_required": self.is_required,
            "file_types": self.file_types,
            "open_mode": self.open_mode,
            "options": self.options,
        }

    def update_config(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_required: Optional[bool] = None,
        options: Optional[List[str]] = None,
        file_types: Optional[List[tuple[str, str]]] = None,
        open_mode: Optional[str] = None,
    ) -> None:
        """
        Updates the control configuration dynamically.
        """
        if name is not None:
            self.name = name
            if hasattr(self, "lbl_name"):
                self.lbl_name.configure(text=name)

        if description is not None:
            self.description = description
            if hasattr(self, "lbl_name"):
                ToolTip(self.lbl_name, text=description, bootstyle="info")

        if is_required is not None:
            self.is_required = is_required
            if hasattr(self, "chk"):
                self.chk.configure(
                    state="disabled" if is_required else "normal",
                    bootstyle=(
                        "success-round-toggle"
                        if is_required
                        else "primary-round-toggle"
                    ),
                )
                if is_required:
                    self.var_enabled.set(True)
                self.toggle_state()

        if options is not None:
            self.options = options
            self._update_options_ui()

        if file_types is not None:
            self.file_types = file_types

        if open_mode is not None:
            self.open_mode = open_mode

    def _update_options_ui(self) -> None:
        """
        Hook for subclasses to update UI when options change.
        """
        pass

    def _build_common_ui(self) -> None:
        """Builds the common UI elements (checkbox and label)
        for all controls."""
        self.chk = tb.Checkbutton(
            self,
            variable=self.var_enabled,
            command=self.toggle_state,
            state="disabled" if self.is_required else "normal",
            bootstyle=(
                "success-round-toggle"
                if self.is_required
                else "primary-round-toggle"
            ),
        )
        self.chk.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.lbl_name = tb.Label(
            self, text=self.name, wraplength=100, anchor="w"
        )
        self.lbl_name.grid(row=0, column=1, padx=(0, 10), sticky="ew")

        if self.description:
            ToolTip(self.lbl_name, text=self.description, bootstyle="info")
