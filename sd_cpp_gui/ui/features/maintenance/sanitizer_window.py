"""
UI for Library Sanitization.
"""

import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END, X, Y

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.domain.maintenance.library_cleaner import LibraryCleanerService
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.utils import CopyLabel, center_window
from sd_cpp_gui.ui.features.maintenance.resolver_dlg import (
    NetworkResolverDialog,
)

logger = get_logger(__name__)


class SanitizerWindow(ttk.Toplevel):
    def __init__(self, parent: tk.Widget) -> None:
        """Logic: Initializes the window, service,
        and starts the initial scan."""
        super().__init__(parent)
        self.title("Library Sanitizer & Migration Tool")
        self.geometry("950x700")
        center_window(self, parent, 950, 700)
        self.service = LibraryCleanerService()
        self.changes: List[Dict[str, Any]] = []
        self._init_ui()
        self._start_scan()

    def _init_ui(self) -> None:
        """Logic: Builds the UI: Header info, Treeview for file changes,
        and Action buttons (Progress bar/Run)."""
        header = ttk.Frame(self, padding=15, bootstyle="primary")
        header.pack(fill=X)
        info_frame = ttk.Frame(header, bootstyle="primary")
        info_frame.pack(side="left")
        CopyLabel(
            info_frame,
            text="Library Sanitizer",
            font=(SYSTEM_FONT, 14, "bold"),
            bootstyle="inverse-primary",
        ).pack(anchor="w")
        CopyLabel(
            info_frame,
            text="Renames files to ASCII (FAT/NTFS safe)"
            " and patches History DB.",
            bootstyle="inverse-primary",
            font=(SYSTEM_FONT, 9),
        ).pack(anchor="w")
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        cols = ("type", "original", "new", "status")
        self.tree = ttk.Treeview(
            list_frame, columns=cols, show="headings", bootstyle="info"
        )
        self.tree.heading("type", text="Type")
        self.tree.heading("original", text="Current Filename")
        self.tree.heading("new", text="New Filename (Disk)")
        self.tree.heading("status", text="Status")
        self.tree.column("type", width=80, stretch=False)
        self.tree.column("original", width=350)
        self.tree.column("new", width=350)
        self.tree.column("status", width=100)
        sb = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill=BOTH, expand=True)
        sb.pack(side="right", fill=Y)
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill=X, side="bottom")
        self.lbl_status = CopyLabel(
            controls, text="Initializing...", font=(SYSTEM_FONT, 10)
        )
        self.lbl_status.pack(side="left")
        self.pb = ttk.Progressbar(
            controls, value=0, maximum=100, mode="determinate"
        )
        self.pb.pack(side="left", fill=X, expand=True, padx=15)
        self.btn_run = flat.RoundedButton(
            controls,
            text="RENAME & PATCH",
            bootstyle="danger",
            width=160,
            command=self._confirm_execution,
        )
        self.btn_run.pack(side="right")

    def _start_scan(self) -> None:
        """Logic: Starts a background thread to scan for filenames
        needing sanitization."""
        self.lbl_status.config(text="Scanning library...")
        self.btn_run.config(state="disabled")

        def _scan() -> None:
            try:
                self.changes = self.service.scan_for_changes()
                self.after(0, self._render_scan_results)
            except Exception as e:
                logger.error(f"Scan failed: {e}", exc_info=True)

        threading.Thread(target=_scan, daemon=True).start()

    def _render_scan_results(self) -> None:
        """Logic: Populates the treeview with proposed file renaming
        changes found by the scanner."""
        self.tree.delete(*self.tree.get_children())
        if not self.changes:
            self.lbl_status.config(
                text="All filenames are portable. No changes needed."
            )
            return
        for item in self.changes:
            self.tree.insert(
                "",
                END,
                values=(
                    item["type"],
                    item["original_filename"],
                    item["new_filename"],
                    "Pending",
                ),
            )
        self.lbl_status.config(text=f"Found {len(self.changes)} files to fix.")
        self.btn_run.config(state="normal")

    def _confirm_execution(self) -> None:
        """Logic: Shows a confirmation dialog detailing the actions (rename,
        patch history) before proceeding."""
        if not self.changes:
            return
        if messagebox.askyesno(
            "Confirm Sanitization",
            f"Ready to rename {len(self.changes)} files?\n\n"
            "• Files on disk will be renamed to ASCII\n"
            "• Metadata/Preview files will be renamed\n"
            "• History Prompts will be updated to match\n\n"
            "The display name (Alias) in the list will stay the same.",
            parent=self,
        ):
            self._execute()

    def _execute(self) -> None:
        """Logic: Runs the sanitization worker thread: renames files,
        patches history, and resolves missing LoRAs."""
        self.btn_run.config(state="disabled")

        def _worker() -> None:
            try:
                mapping = self.service.execute_renames(
                    self.changes, self._update_progress
                )
                renamed_count = 0
                if mapping:
                    self._update_progress(
                        0, 1, "Patching renames in History..."
                    )
                    renamed_count = self.service.patch_history(
                        mapping, self._update_progress
                    )
                self._update_progress(0, 1, "Scanning for missing LoRAs...")

                def ask_user(
                    missing_name: str, options: List[str]
                ) -> Optional[str]:
                    result_holder = [None]
                    event = threading.Event()

                    def _show_dialog():
                        dialog = NetworkResolverDialog(
                            self, missing_name, "LoRA", options
                        )
                        self.wait_window(dialog)
                        result_holder[0] = dialog.result
                        event.set()

                    self.after(0, _show_dialog)
                    event.wait()
                    return result_holder[0]

                absent_fixed_count = self.service.fix_absent_loras(
                    resolver_callback=ask_user,
                    progress_callback=self._update_progress,
                )
                total_patched = renamed_count + absent_fixed_count
                self.after(0, lambda: self._finish(len(mapping), total_patched))
            except Exception as e:
                logger.error(f"Worker failed: {e}", exc_info=True)

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, current: int, total: int, msg: str) -> None:
        """Logic: Schedules UI update for progress bar and status
        label on main thread."""
        self.after(0, lambda: self._do_update_ui(current, total, msg))

    def _do_update_ui(self, current: int, total: int, msg: str) -> None:
        """Logic: Updates the progress bar value and status text."""
        pct = current / total * 100 if total > 0 else 0
        self.pb["value"] = pct
        self.lbl_status.config(text=f"{msg}")

    def _finish(self, renamed: int, patched: int) -> None:
        """Logic: Shows completion message and closes the window."""
        self.lbl_status.config(text="Completed.")
        self.pb["value"] = 100
        messagebox.showinfo(
            "Sanitization Complete",
            f"Renamed {renamed} files.\nPatched {patched} history entries.",
            parent=self,
        )
        self.destroy()
