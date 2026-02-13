"""
Funções utilitárias compartilhadas pela interface.
"""

from __future__ import annotations

import tkinter as tk
import traceback

import ttkbootstrap as ttk


class CopyLabel(ttk.Label):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._create_context_menu()

        # Bind click event
        trigger = (
            "<Button-2>"
            if self.tk.call("tk", "windowingsystem") == "aqua"
            else "<Button-3>"
        )
        self.bind(trigger, self._show_context_menu)

    def _create_context_menu(self):
        self.context_menu = tk.Menu(
            self, tearoff=0, borderwidth=0, relief="flat"
        )
        self.context_menu.add_command(
            label="Copy", command=self.copy_to_clipboard
        )

    def _show_context_menu(self, event):
        self.context_menu.tk_popup(event.x_root + 1, event.y_root + 1)

    def copy_to_clipboard(self, _event=None):
        text = self.cget("text")

        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()


def center_window(
    window: tk.Tk, parent: tk.Misc, width: int, height: int
) -> None:
    """
    Centraliza uma janela Toplevel em relação ao seu pai.

    Logic: Calculates coordinates to center window relative to parent,
    falling back to screen center."""
    window.update_idletasks()
    try:
        p_x = parent.winfo_rootx()
        p_y = parent.winfo_rooty()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()
        x = p_x + p_w // 2 - width // 2
        y = p_y + p_h // 2 - height // 2
        window.geometry(f"{width}x{height}+{x}+{y}")
    except (tk.TclError, ValueError):
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = screen_w // 2 - width // 2
        y = screen_h // 2 - height // 2
        window.geometry(f"{width}x{height}+{x}+{y}")


def restore_sash(settings, sash_name: str, window: tk.PanedWindow):
    """Logic: Restores PanedWindow sash position from settings."""
    pos = settings.get(f"{sash_name}_sash_position")
    if pos:
        try:
            if window.winfo_exists():
                if hasattr(window, "sashpos"):
                    window.sashpos(0, int(pos))
                elif hasattr(window, "sash_place"):
                    window.sash_place(0, int(pos), 0)
        except tk.TclError:
            pass


def save_sash_position(settings, sash_name: str, window: tk.Panedwindow):
    """Logic: Saves current PanedWindow sash position to settings."""
    try:
        if window.winfo_exists():
            if hasattr(window, "sashpos"):
                pos = window.sashpos(0)
            elif hasattr(window, "sash_coord"):
                pos = window.sash_coord(0)[0]
            else:
                return
            settings.set(f"{sash_name}_sash_position", pos)
    except (tk.TclError, IndexError, KeyError):
        traceback.print_exc()
