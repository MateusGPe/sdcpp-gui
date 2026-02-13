"""
Choice (Enum/List) Argument Control
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import ttkbootstrap as tb

from sd_cpp_gui.ui.controls.base import BaseArgumentControl

if TYPE_CHECKING:
    pass


class ChoiceControl(BaseArgumentControl):
    """A control for arguments with a predefined list of choices (Enum)."""

    def _build_ui(self) -> None:
        """Builds the UI for a choice/combobox control.

        Logic: Builds common UI and adds a read-only Combobox."""
        self._build_common_ui()
        self.input_widget = tb.Combobox(
            self,
            textvariable=self.var_value,
            values=self.options,
            state="readonly",
        )
        self.input_widget.grid(row=0, column=2, sticky="ew")
