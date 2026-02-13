from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from sd_cpp_gui.ui.components.color_manager import ColorManager


class SuggestionPopup(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        on_select_callback: Callable[[str], None],
        color_manager: ColorManager,
    ) -> None:
        """Logic: Initializes popup window, listbox, and bindings."""
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(parent.winfo_toplevel())
        self.on_select = on_select_callback
        self.cm = color_manager
        self.current_selection_index = 0
        self._current_values: List[str] = []
        self.border_frame = tk.Frame(self, bd=1, relief="solid")
        self.border_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(
            self.border_frame,
            height=6,
            font=("Segoe UI", 10),
            bd=0,
            highlightthickness=0,
            activestyle="none",
            exportselection=False,
            cursor="hand2",
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        self.listbox.bind("<ButtonRelease-1>", self._confirm_selection)
        self.listbox.bind("<Motion>", self._on_mouse_hover)

    def show(
        self,
        x: int,
        y: int,
        width: int,
        items: List[Union[str, Tuple[str, str]]],
        autolayout: bool = True,
        initial_index: int = 0,
    ) -> None:
        """
        Logic: Populates listbox, calculates position/size, and shows popup.
        """
        if not items:
            self.hide()
            return
        self._current_values = []
        display_items = []
        measure_font = tkfont.Font(font=self.listbox.cget("font"))
        max_text_width = 0
        for item in items:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                display_items.append(item[0])
                self._current_values.append(item[1])
                w = measure_font.measure(item[0])
            else:
                display_items.append(str(item))
                self._current_values.append(str(item))
                w = measure_font.measure(str(item))
            if w > max_text_width:
                max_text_width = w
        p = self.cm.palette
        bg_col = p["bg"]
        fg_col = self.cm.ensure_contrast(bg_col, "#333333")
        sel_bg = self.cm.overrides.get("focus") or "#007acc"
        sel_fg = "#ffffff"
        border_col = p["border"]
        self.border_frame.configure(bg=border_col)
        self.listbox.configure(
            bg=bg_col,
            fg=fg_col,
            selectbackground=sel_bg,
            selectforeground=sel_fg,
        )

        self.listbox.delete(0, tk.END)
        for label in display_items:
            self.listbox.insert(tk.END, label)

        self.current_selection_index = initial_index
        self.listbox.selection_set(initial_index)
        self.listbox.see(initial_index)
        item_height = 24
        req_height = min(len(display_items), 8) * item_height + 4
        final_width = max(width, max_text_width + 30)
        screen_h = self.winfo_screenheight()

        if autolayout:
            parent_h = self.master.winfo_height() if self.master else 48
            pos_below = y + parent_h
            pos_above = y - req_height
            if pos_below + req_height > screen_h:
                target_y = pos_above
            else:
                target_y = pos_below
        else:
            target_y = y
            if target_y + req_height > screen_h:
                target_y = y - req_height

        self.geometry(f"{final_width}x{req_height}+{x}+{target_y}")
        self.deiconify()
        self.lift()

    def hide(self) -> None:
        """Logic: Hides popup."""
        self.withdraw()

    def _confirm_selection(self, _event: Optional[tk.Event] = None) -> None:
        """Logic: Triggers selection callback."""
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self._current_values):
                val = self._current_values[index]
                self.on_select(val)
                self.hide()

    def _on_mouse_hover(self, event: tk.Event) -> None:
        """Logic: Updates selection based on mouse position."""
        index = self.listbox.nearest(event.y)
        if (
            0 <= index < self.listbox.size()
            and self.current_selection_index != index
        ):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(index)
            self.current_selection_index = index

    def move_selection(self, direction: int) -> Tuple[int, int]:
        """Logic: Moves selection up/down."""
        if self.state() != "normal":
            return (0, 0)

        max_index = self.listbox.size() - 1
        new_index = self.current_selection_index + direction
        end_of_list = new_index
        new_index = max(0, min(new_index, max_index))

        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(new_index)
        self.listbox.see(new_index)
        self.current_selection_index = new_index
        return (end_of_list, max_index)

    def get_current_selection(self) -> Optional[str]:
        """Logic: Returns currently selected text."""
        if self.state() != "normal":
            return None
        try:
            return self._current_values[self.current_selection_index]
        except Exception:
            return None
