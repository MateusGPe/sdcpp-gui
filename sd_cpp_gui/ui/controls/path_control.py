"""
Path Argument Control
"""

from __future__ import annotations

from tkinter import StringVar, filedialog
from typing import TYPE_CHECKING

from sd_cpp_gui.constants import CORNER_RADIUS
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.entry import MEntry
from sd_cpp_gui.ui.controls.base import BaseArgumentControl

if TYPE_CHECKING:
    pass
logger = get_logger("PathControl")


class PathControl(BaseArgumentControl):
    """A control for file or directory path arguments."""

    def _build_ui(self) -> None:
        """Builds the UI for a path input control with a browse button.

        Logic: Builds common UI, adds entry for path, and a browse button."""
        self._build_common_ui()
        self.input_widget = MEntry(
            self,
            textvariable=self.var_value,
            height=50,
            radius=CORNER_RADIUS,
            elevation=2,
        )
        self.input_widget.grid(row=0, column=2, sticky="ew", padx=(0, 5))
        icon = "📂" if self.open_mode == "directory" else "📄"
        btn_browse = flat.RoundedButton(
            self,
            text=icon,
            width=50,
            height=50,
            corner_radius=CORNER_RADIUS,
            bootstyle="secondary",
            command=self._browse_path,
        )
        btn_browse.grid(row=0, column=3, sticky="e")
        if not self.file_types:
            self.file_types = [("All", "*.*")]

    def _browse_path(self) -> None:
        """Opens the appropriate file/directory dialog.
        Logic: Opens file/directory chooser based on open_mode and
        sets the variable."""
        filename = ""
        if self.open_mode == "directory":
            filename = filedialog.askdirectory(parent=self)
        elif self.open_mode == "file_save":
            filename = filedialog.asksaveasfilename(
                parent=self,
                defaultextension=".png",
                filetypes=self.file_types
                or [("Images", "*.png *.jpg"), ("All", "*.*")],
            )
        else:
            filename = filedialog.askopenfilename(
                filetypes=self.file_types, parent=self
            )
        if filename:
            assert isinstance(self.var_value, StringVar)
            self.var_value.set(filename)
            logger.info("Path selected for '%s': %s", self.name, filename)
