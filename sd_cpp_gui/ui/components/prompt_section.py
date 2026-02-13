"""
Prompt Section Component.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

import ttkbootstrap as ttk

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.domain.services.autocomplete_service import AutocompleteService
from sd_cpp_gui.ui.components.color_manager import ColorManager
from sd_cpp_gui.ui.components.prompt_highlighter import PromptHighlighter
from sd_cpp_gui.ui.components.utils import CopyLabel


class PromptSection(ttk.Frame):
    """
    A labeled section with a syntax-highlighting text area.
    """

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        color_manager: ColorManager,
        autocomplete_service: Optional[AutocompleteService] = None,
        height: int = 80,
    ) -> None:
        super().__init__(parent)
        CopyLabel(
            self,
            text=label,
            font=(SYSTEM_FONT, 9, "bold"),
            bootstyle="secondary",
        ).pack(anchor="w")

        self.highlighter = PromptHighlighter(
            self,
            height=height,
            autocomplete_service=autocomplete_service,
        )
        self.highlighter.pack(fill=tk.BOTH, expand=True, pady=(2, 10))

    def get_text(self) -> str:
        return self.highlighter.get("1.0", "end-1c")

    def set_text(self, text: str) -> None:
        self.highlighter.set_text(text)
        self.highlighter.highlight()
