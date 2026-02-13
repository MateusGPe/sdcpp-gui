"""
String (Text) Argument Control
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sd_cpp_gui.constants import CORNER_RADIUS
from sd_cpp_gui.ui.components.entry import MEntry
from sd_cpp_gui.ui.controls.base import BaseArgumentControl

if TYPE_CHECKING:
    pass


class StringControl(BaseArgumentControl):
    """A control for string-based arguments."""

    def _build_ui(self) -> None:
        """Builds the UI for a string input control.

        Logic: Builds common UI and adds an MEntry widget for text input."""
        self._build_common_ui()
        self.input_widget = MEntry(
            self,
            textvariable=self.var_value,
            height=50,
            radius=CORNER_RADIUS,
            elevation=2,
        )
        self.input_widget.grid(row=0, column=2, sticky="ew")
