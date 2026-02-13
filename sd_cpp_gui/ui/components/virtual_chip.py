from __future__ import annotations

import inspect
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional

from sd_cpp_gui.ui.components.nine_slices import NineSliceRenderer


def get_caller_info(stack_depth=2):
    """
    Returns information about the caller in the stack.
    depth=1 is this function.
    depth=2 is the immediate caller.
    """
    stack = inspect.stack()

    # Ensure we don't go out of bounds
    if len(stack) < stack_depth + 1:
        return "No caller found (Top Level)"

    # Get the frame record for the requested depth
    frame_record = stack[stack_depth]

    # frame_record is a named tuple containing:
    # (frame, filename, lineno, function, code_context, index)
    return {
        "function": frame_record.function,
        "filename": frame_record.filename,
        "line": frame_record.lineno,
        "context": frame_record.code_context[0].strip()
        if frame_record.code_context
        else None,
    }


class VirtualChip:
    def __init__(self, text: str, variant: str, font: tuple):
        self._text = text
        self.variant = variant
        self.font = font
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0
        self.selected = False
        self.hovering = False
        self.dragging = False
        self.drop_target = False
        self.tag_prefix = f"chip_{id(self)}"
        self.renderer = NineSliceRenderer(radius=8, border_width=0, elevation=0)
        self.wrap_width: Optional[int] = None
        self.update_size()

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value

    def update_size(self, max_width: Optional[int] = None):
        font_obj = tkfont.Font(font=self.font)
        padding_x = 35
        line_height = font_obj.metrics("linespace")

        # Handle explicit newlines
        physical_lines = self._text.split("\n")

        # Calculate max width among all physical lines
        max_line_width = 0
        for line in physical_lines:
            w = font_obj.measure(line)
            if w > max_line_width:
                max_line_width = w
        self.text_width = max_line_width

        if max_width and (self.text_width + padding_x) > max_width:
            self.wrap_width = max_width - padding_x
            if self.wrap_width < 10:
                self.wrap_width = 10

            total_visual_lines = 0
            space_w = font_obj.measure(" ")

            for line in physical_lines:
                if not line:
                    total_visual_lines += 1
                    continue

                current_w = 0
                line_lines = 1
                for word in line.split():
                    word_w = font_obj.measure(word)
                    if current_w + word_w > self.wrap_width:
                        line_lines += 1
                        current_w = word_w + space_w
                    else:
                        current_w += word_w + space_w
                total_visual_lines += line_lines

            self.h = max(24, total_visual_lines * line_height + 12)
            self.w = max_width
        else:
            num_lines = len(physical_lines)
            self.wrap_width = None
            if max_width and num_lines > 1:
                self.w = max_width
            else:
                self.w = self.text_width + padding_x
            self.h = max(24, num_lines * line_height + 12)

    def destroy(self, canvas: tk.Canvas) -> None:
        """Removes all canvas items associated with this chip."""
        suffixes = [
            "c",
            "tl",
            "tr",
            "bl",
            "br",
            "t",
            "b",
            "l",
            "r",
            "text",
            "close",
        ]
        for suffix in suffixes:
            canvas.delete(f"{self.tag_prefix}_{suffix}")

    def set_visible(self, canvas: tk.Canvas, visible: bool) -> None:
        """Sets the visibility of the chip's canvas items."""
        state = "normal" if visible else "hidden"
        suffixes = [
            "c",
            "tl",
            "tr",
            "bl",
            "br",
            "t",
            "b",
            "l",
            "r",
            "text",
            "close",
        ]
        for suffix in suffixes:
            canvas.itemconfigure(f"{self.tag_prefix}_{suffix}", state=state)
