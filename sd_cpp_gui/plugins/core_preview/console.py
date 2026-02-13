from __future__ import annotations

import queue
from queue import SimpleQueue
from typing import Any, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END

from sd_cpp_gui.ui.components import text


class LogConsole(ttk.Frame):
    """Displays application logs with syntax highlighting."""

    COLORS = {
        "RAW": "#dcdccc",
        "INFO": "#87ceeb",
        "SUCCESS": "#98c379",
        "WARNING": "#e5c07b",
        "ERROR": "#e06c75",
        "SYSTEM": "#c678dd",
        "PROGRESS": "#56b6c2",
    }

    def __init__(self, parent: Any, **kwargs: Any) -> None:
        """Logic: Initializes console."""
        super().__init__(parent, **kwargs)
        self.log_queue: SimpleQueue[Tuple[str, str]] = queue.SimpleQueue()
        self._log_poll_id: Optional[str] = None
        self.txt_widget = text.MText(
            self,
            bg_color="#1e1e1e",
            fg_color="#dcdccc",
            width=400,
            height=120,
            font=("Consolas", 8),
        )
        self.txt_widget.pack(fill=BOTH, expand=True)
        self.txt_widget.configure(
            insertbackground="white", selectbackground="gray", state="disabled"
        )
        self._setup_tags()
        self._poll_log_queue()

    def _setup_tags(self) -> None:
        """Logic: Sets up tags."""
        for tag_name, color in self.COLORS.items():
            self.txt_widget.tag_config(tag_name, foreground=color)
        self.txt_widget.tag_config("DIM", foreground="#5c6370")

    def log(self, text: str, msg_type: str = "RAW") -> None:
        """Logic: Logs text."""
        self.log_queue.put((msg_type, text))

    def clear(self) -> None:
        """Logic: Clears console."""
        self.txt_widget.configure(state="normal")
        self.txt_widget.delete("1.0", END)
        self.txt_widget.configure(state="disabled")

    def _poll_log_queue(self) -> None:
        """Logic: Polls log queue."""
        if not self.log_queue.empty():
            self.txt_widget.configure(state="normal")
            while not self.log_queue.empty():
                try:
                    msg_type, text = self.log_queue.get_nowait()
                    tag = msg_type if msg_type in self.COLORS else "RAW"
                    self.txt_widget.insert(END, text.rstrip() + "\n", tag)
                except queue.Empty:
                    break
            self.txt_widget.see(END)
            self.txt_widget.configure(state="disabled")
        if self.winfo_exists():
            self._log_poll_id = self.after(100, self._poll_log_queue)
