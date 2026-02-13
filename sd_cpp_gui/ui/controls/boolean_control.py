"""
Boolean (Flag) Argument Control
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

import ttkbootstrap as tb

from sd_cpp_gui.ui.controls.base import BaseArgumentControl

if TYPE_CHECKING:
    pass


class BooleanControl(BaseArgumentControl):
    """A control for boolean arguments, typically represented as a flag."""

    def _build_ui(self) -> None:
        """Builds the UI for a boolean/flag control.

        Logic: Creates a checkbutton and label for the flag."""
        self.chk = tb.Checkbutton(
            self, variable=self.var_enabled, bootstyle="round-toggle"
        )
        self.chk.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.lbl_name = tb.Label(
            self, text=self.name, wraplength=150, anchor="w"
        )
        self.lbl_name.grid(row=0, column=1, padx=(0, 10), sticky="w")
        if self.description:
            tb.widgets.ToolTip(
                self.lbl_name, text=self.description, bootstyle="info"
            )
        tb.Label(self, text="(Flag)", bootstyle="secondary").grid(
            row=0, column=2, sticky="w"
        )
        self.input_widget = None

    def get_command_arg(self) -> Optional[Tuple[str, str]]:
        """Returns the command-line flag if enabled.

        Logic: Returns flag if enabled, else None."""
        if not self.var_enabled.get():
            return None
        return (self.flag, "")

    def _do_toggle_state(self) -> None:
        """No specific input widget to toggle for flags."""
        pass
