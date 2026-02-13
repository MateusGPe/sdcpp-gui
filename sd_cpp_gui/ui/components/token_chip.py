from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import TYPE_CHECKING, Callable, Optional

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.ui.components.color_manager import blend_colors

if TYPE_CHECKING:
    from sd_cpp_gui.ui.components.color_manager import ColorManager
    from sd_cpp_gui.ui.components.nine_slices import (
        NineSliceRenderer,
    )


class TokenChip(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        on_remove: Callable[[], None],
        color_manager: ColorManager,
        focus_callback: Callable[[], None],
        renderer: NineSliceRenderer,
        variant: str = "default",
        font: tuple = (SYSTEM_FONT, 9, "bold"),
    ) -> None:
        """
        Initializes chip widget with text and close button.
        """
        super().__init__(parent, bd=0, highlightthickness=0, height=24)
        self.text = text
        self.color_manager = color_manager
        self.on_remove = on_remove
        self.focus_callback = focus_callback
        self.variant = variant
        self._is_selected = False
        self._is_hovering = False
        self._is_dragging = False
        self._is_drop_target = False
        self.bg_color = "#ffffff"
        self.fg_color = "#000000"
        self.border_color = "#000000"
        self.renderer = renderer
        self.font = font
        font_obj = tkfont.Font(font=self.font)
        text_width = font_obj.measure(text)
        self.width = text_width + 35
        self.configure(width=self.width)
        self.bind("<Configure>", self._draw)
        self.bind("<Button-1>", lambda _e: self.focus_callback())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.update_colors()

    def update_color_palette(self, override_bg: Optional[str] = None) -> None:
        """
        Updates colors based on state (selected, hover, variant).
        Args:
            override_bg: Optional base color provided by subclass (e.g.
            variant color).
        """
        # 1. Update palette to ensure we have fresh theme context
        p = self.color_manager.update_palette()
        container_bg = p["bg"]

        # 2. Resolve Theme Colors
        # Use 'primary' for selection, and standard FG/BG for base
        primary = self.color_manager._resolve_color("primary")
        fg_default = self.color_manager._resolve_color("fg")

        # 3. Calculate Base Background
        # If subclass provided a color (e.g. "Orange" for numbers), use it.
        # Otherwise, derive a surface color from FG/BG.
        if override_bg:
            base_bg = override_bg
        else:
            base_bg = blend_colors(fg_default, container_bg, 0.1)

        # 4. Determine State Colors (Layering state on top of base)
        if self._is_dragging:
            # Dragging: Dimmed/Ghosted appearance
            self.bg_color = blend_colors(primary, container_bg, 0.6)
            self.fg_color = self.color_manager.ensure_contrast(
                self.bg_color, fg_default
            )
            self.border_color = self.bg_color
        elif self._is_drop_target:
            # Drop Target: Highlighted
            self.bg_color = blend_colors(primary, container_bg, 0.3)
            self.fg_color = self.color_manager.ensure_contrast(
                self.bg_color, fg_default
            )
            self.border_color = primary
        elif self._is_selected:
            # Selected: Use Primary color
            self.bg_color = blend_colors(base_bg, primary, 0.6)
            # Ensure text is readable on Primary (usually white)
            self.fg_color = self.color_manager.ensure_contrast(
                self.bg_color, primary
            )
            self.border_color = primary
        elif self._is_hovering:
            # Hover: Mix 20% of Primary into Base BG for a subtle tint
            self.bg_color = blend_colors(primary, base_bg, 0.2)
            self.fg_color = self.color_manager.ensure_contrast(
                self.bg_color, fg_default
            )
            self.border_color = self.bg_color
        else:
            # Default
            self.bg_color = base_bg
            self.fg_color = self.color_manager.ensure_contrast(
                self.bg_color, fg_default
            )
            self.border_color = base_bg
        self.configure(bg=container_bg)

    def update_colors(self) -> None:
        """
        Updates colors based on state (selected, hover, variant).
        """
        self.update_color_palette()
        self._draw()

    def set_selected(self, selected: bool) -> None:
        """
        Sets selection state.
        """
        self._is_selected = selected
        self.update_colors()

    def set_dragging(self, dragging: bool) -> None:
        """
        Sets dragging state.
        """
        self._is_dragging = dragging
        self.update_colors()

    def set_drop_target(self, active: bool) -> None:
        """
        Sets drop target state.
        """
        self._is_drop_target = active
        self.update_colors()

    def set_text(self, text: str) -> None:
        """
        Updates the text content and recalculates width.
        """
        self.text = text
        font_obj = tkfont.Font(font=self.font)
        text_width = font_obj.measure(text)
        self.width = text_width + 35
        self.configure(width=self.width)
        self.update_colors()

    def set_variant(self, variant: str) -> None:
        """
        Updates the visual variant.
        """
        self.variant = variant
        self.update_colors()

    def set_font(self, font: tuple) -> None:
        """
        Updates the font and recalculates width.
        """
        self.font = font
        self.set_text(self.text)

    def _on_enter(self, _event: tk.Event) -> None:
        """
        Sets hover state.
        """
        self._is_hovering = True
        self.update_colors()

    def _on_leave(self, _event: tk.Event) -> None:
        """
        Unsets hover state.
        """
        self._is_hovering = False
        self.update_colors()

    def _draw(self, _event: Optional[tk.Event] = None) -> None:
        """
        Draws the chip using nine-slice renderer and text.
        """
        try:
            w = self.winfo_width()
            h = self.winfo_height()
            if w < 1 or h < 1:
                return

            render_palette = {
                "bg": self.bg_color,
                "bg_base": self.bg_color,
                "bg_hover": self.bg_color,
                "border": self.border_color,
                "shadow": "#000000",
                "parent": self.cget("bg"),
            }
            self.renderer.generate_slices(render_palette)
            self.renderer.draw_on_canvas(self, w, h)
            self.delete("content")

            # Draw Text
            self.create_text(
                10,
                h / 2,
                text=self.text,
                anchor="w",
                fill=self.fg_color,
                font=self.font,
                tags=("content", "text_body"),  # Added specific tag
            )

            # Draw Close Button
            self.create_text(
                w - 10,
                h / 2 - 1,
                text="×",
                anchor="e",
                fill=self.fg_color,
                font=(
                    self.font[0],
                    max(self.font[1] - 1, 6) if len(self.font) > 2 else 8,
                ),
                tags=("content", "close_btn"),
            )
            self.tag_bind("close_btn", "<Button-1>", lambda e: self.on_remove())
            self.tag_bind(
                "close_btn", "<Enter>", lambda e: self.configure(cursor="hand2")
            )
            self.tag_bind(
                "close_btn", "<Leave>", lambda e: self.configure(cursor="arrow")
            )

            # Bind click on body to focus
            self.tag_bind(
                "text_body", "<Button-1>", lambda e: self.focus_callback()
            )

        except tk.TclError:
            pass
