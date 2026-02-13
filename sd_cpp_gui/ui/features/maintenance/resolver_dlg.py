"""
Interactive Migration Tool: Backfill 'used_networks' and Fix Broken Links.

Features:
1. Scans History for LoRA/Embedding tags.
2. Matches them against the local library.
3. If a network is MISSING, opens a GUI to ask the user to map it to a new file.
4. Updates 'metadata.used_networks' (for UI display).
5. Updates 'prompt' text (renaming the tag <lora:old:1> to <lora:new:1>).
"""

import tkinter as tk
from typing import List, Optional

import ttkbootstrap as ttk

from sd_cpp_gui.ui.components.entry import MEntry
from sd_cpp_gui.ui.components.utils import CopyLabel


class NetworkResolverDialog(ttk.Toplevel):
    """
    Modal dialog to help the user resolve a missing network.
    """

    def __init__(
        self,
        parent,
        missing_name: str,
        network_type: str,
        available_items: List[str],
    ):
        """Logic: Initializes the modal dialog, sets up data, and builds UI."""
        super().__init__(parent)
        self.title(f"Resolve Missing {network_type}")
        self.geometry("600x500")
        self.result: Optional[str] = None
        self.missing_name = missing_name
        self.available_items = available_items
        self.filtered_items = available_items
        self._init_ui()
        self._center_window(parent)
        self.transient(parent)
        self.grab_set()
        self.lift()
        self.focus_force()

    def _init_ui(self):
        """Logic: Creates UI elements: Header info, Search bar,
        Listbox of available items, and Action buttons."""
        CopyLabel(
            self,
            text=f"Missing: '{self.missing_name}'",
            bootstyle="danger",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=10)
        CopyLabel(
            self,
            text="Select the correct file from your library to map it:",
            bootstyle="secondary",
        ).pack(pady=(0, 5))
        self.var_search = tk.StringVar()
        self.var_search.trace("w", self._on_search)
        entry_search = MEntry(
            self, textvariable=self.var_search, bootstyle="info"
        )
        entry_search.pack(fill=tk.X, padx=10, pady=5)
        entry_search.bind("<Return>", lambda e: self._confirm())
        frame_list = ttk.Frame(self)
        frame_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.listbox = tk.Listbox(
            frame_list, height=15, selectmode=tk.SINGLE, font=("Consolas", 10)
        )
        sb = ttk.Scrollbar(
            frame_list, orient=tk.VERTICAL, command=self.listbox.yview
        )
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._refresh_list()
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(
            btn_frame,
            text="Skip (Leave as Ghost)",
            bootstyle="secondary",
            command=self._skip,
        ).pack(side=tk.LEFT)
        ttk.Button(
            btn_frame,
            text="Confirm Mapping",
            bootstyle="success",
            command=self._confirm,
        ).pack(side=tk.RIGHT)

    def _center_window(self, parent):
        """Logic: Centers the dialog relative to the parent window."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = parent.winfo_rootx() + parent.winfo_width() // 2 - width // 2
        y = parent.winfo_rooty() + parent.winfo_height() // 2 - height // 2
        if x < 0:
            x = self.winfo_screenwidth() // 2 - width // 2
        if y < 0:
            y = self.winfo_screenheight() // 2 - height // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _on_search(self, *args):
        """Logic: Filters the listbox items based on the search entry input."""
        query = self.var_search.get().lower()
        if not query:
            self.filtered_items = self.available_items
        else:
            self.filtered_items = [
                item for item in self.available_items if query in item.lower()
            ]
        self._refresh_list()

    def _refresh_list(self):
        """Logic: Clears and repopulates the listbox with filtered items."""
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            self.listbox.insert(tk.END, item)

    def _confirm(self):
        """Logic: Sets the selected item as the result and closes the dialog."""
        sel = self.listbox.curselection()
        if sel:
            self.result = self.listbox.get(sel[0])
            self.destroy()

    def _skip(self):
        """Logic: Sets result to None (skip mapping) and closes the dialog."""
        self.result = None
        self.destroy()
