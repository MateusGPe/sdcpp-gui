"""
Detail Panel for the History Window.
"""

from __future__ import annotations

import json
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, VERTICAL, X, Y

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.data.db.models import HistoryData
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import flat, text
from sd_cpp_gui.ui.components.prompt_highlighter import PromptHighlighter
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.domain.generation.commands_loader import CommandLoader
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class HistoryDetailPanel(ttk.Frame):
    """
    The right-side panel in the HistoryWindow,
    showing details of a selected item.
    """

    # pylint: disable=too-many-ancestors, too-many-instance-attributes
    def __init__(
        self,
        parent: ttk.Panedwindow,
        cmd_loader: CommandLoader,
        restore_callback: Callable[[], None],
        copy_callback: Callable[[], None],
        **kwargs: Any,
    ):
        """Logic: Initializes panel, callbacks, builds UI with tabs,
        and clears view."""
        super().__init__(parent, padding=(10, 0), bootstyle="bg", **kwargs)
        self.cmd_loader = cmd_loader
        self.restore_callback = restore_callback
        self.copy_callback = copy_callback
        self.notebook: ttk.Notebook
        self.tab_preview: ttk.Frame
        self.tab_params: ttk.Frame
        self.tab_meta: ttk.Frame
        self.lbl_big_img: CopyLabel
        self.txt_prompt: PromptHighlighter
        self.tree_params: ttk.Treeview
        self.txt_meta: text.MText
        self.btn_restore: flat.RoundedButton
        self.btn_copy: flat.RoundedButton
        self.image: Optional[ImageTk.PhotoImage] = None
        self._build_ui()
        self.clear_view()

    def _build_ui(self) -> None:
        """Builds the entire detail panel UI,
        including tabs and action buttons.

        Logic: Creates Tabs (Preview, Params, Meta) and Action
        Buttons (Restore, Copy)."""
        self.notebook = ttk.Notebook(self, bootstyle="primary")
        self.tab_preview = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(
            self.tab_preview, text=i18n.get("history.tab.preview")
        )
        self._build_tab_preview(self.tab_preview)
        self.tab_params = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_params, text=i18n.get("history.tab.params"))
        self._build_tab_params(self.tab_params)
        self.tab_meta = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_meta, text=i18n.get("history.tab.meta"))
        self._build_tab_meta(self.tab_meta)
        act_row = ttk.Frame(self, padding=(0, 10))
        act_row.pack(fill=X, side=tk.BOTTOM)
        self.btn_restore = flat.RoundedButton(
            act_row,
            text=i18n.get("history.btn.restore"),
            height=50,
            corner_radius=CORNER_RADIUS,
            bootstyle="success",
            command=self.restore_callback,
        )
        self.btn_restore.pack(side=RIGHT)
        self.btn_copy = flat.RoundedButton(
            act_row,
            text=i18n.get("history.btn.copy"),
            bootstyle="info",
            height=50,
            corner_radius=CORNER_RADIUS,
            command=self.copy_callback,
        )
        self.btn_copy.pack(side=RIGHT, padx=10)
        self.notebook.pack(fill=BOTH, expand=True)

    def _build_tab_preview(self, parent: ttk.Frame) -> None:
        """Logic: Builds the Preview tab with image display and
        full prompt text area."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        img_bg = ttk.Frame(parent, bootstyle="dark")
        img_bg.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.lbl_big_img = CopyLabel(
            img_bg, anchor="center", bootstyle="inverse-dark"
        )
        self.lbl_big_img.pack(fill=BOTH, expand=True, padx=1, pady=1)
        lbl_p = CopyLabel(
            parent,
            text=i18n.get("history.lbl.full_prompt"),
            font=(SYSTEM_FONT, 10, "bold"),
        )
        lbl_p.grid(row=1, column=0, sticky="w")
        self.txt_prompt = PromptHighlighter(
            parent,
            height=100,
            font=(SYSTEM_FONT, 10),
            wrap="word",
            padx=5,
            pady=5,
        )
        self.txt_prompt.grid(row=2, column=0, sticky="ew", pady=(5, 0))

    def _build_tab_params(self, parent: ttk.Frame) -> None:
        """Logic: Builds the Params tab with a Treeview
        for generation parameters."""
        cols = ("param", "val")
        self.tree_params = ttk.Treeview(
            parent,
            columns=cols,
            show="headings",
            selectmode="browse",
            bootstyle="info",
        )
        self.tree_params.heading("param", text=i18n.get("history.col.param"))
        self.tree_params.heading("val", text=i18n.get("history.col.value"))
        self.tree_params.column("param", width=200, anchor="w")
        self.tree_params.column("val", width=400, anchor="w")
        sb = ttk.Scrollbar(
            parent, orient=VERTICAL, command=self.tree_params.yview
        )
        self.tree_params.configure(yscrollcommand=sb.set)
        self.tree_params.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side=RIGHT, fill=Y)

    def _build_tab_meta(self, parent: ttk.Frame) -> None:
        """Logic: Builds the Meta tab with a text area for raw JSON metadata."""
        lbl = CopyLabel(
            parent,
            text=i18n.get("history.lbl.raw_json"),
            font=(SYSTEM_FONT, 9, "bold"),
        )
        lbl.pack(anchor="w", pady=(0, 5))
        self.txt_meta = text.MText(parent, font=("Consolas", 9), wrap="word")
        self.txt_meta.pack(side=LEFT, fill=BOTH, expand=True)

    def show_details(self, entry_data: HistoryData) -> None:
        """Populates all the detail fields with data from a history entry.

        Logic: Enables buttons and populates all three tabs with entry data."""
        self.btn_restore.configure(state="normal")
        self.btn_copy.configure(state="normal")
        self._show_details_preview(entry_data)
        self._show_details_params(entry_data)
        self._show_details_meta(entry_data)

    def _show_details_preview(self, entry_data: HistoryData) -> None:
        """Logic: Loads the full-size image (resizing to fit) and
        sets the prompt text."""
        self.txt_prompt.delete("1.0", "end")
        self.txt_prompt.insert("1.0", entry_data.get("prompt", ""))
        self.txt_prompt.highlight()
        paths = entry_data.get("output_path", [])
        path = paths[0] if isinstance(paths, list) and paths else paths
        if (
            path
            and isinstance(path, str)
            and tk.Misc.winfo_exists(self.lbl_big_img)
            and (self.lbl_big_img.winfo_width() > 1)
        ):
            try:
                with Image.open(path) as pil_img:
                    w = self.lbl_big_img.winfo_width()
                    h = self.lbl_big_img.winfo_height()
                    ratio = min(w / pil_img.width, h / pil_img.height, 1.0)
                    new_size = (
                        int(pil_img.width * ratio),
                        int(pil_img.height * ratio),
                    )
                    resized_img = pil_img.resize(
                        new_size, Image.Resampling.LANCZOS
                    )
                    self.image = ImageTk.PhotoImage(resized_img)
                    self.lbl_big_img.configure(image=self.image, text="")
            except (IOError, OSError) as e:
                self.lbl_big_img.configure(image=None, text=str(e))
                self.image = None
        else:
            self.lbl_big_img.configure(
                image=None, text=i18n.get("history.msg.file_not_found")
            )

    def _show_details_params(self, entry_data: HistoryData) -> None:
        """Logic: Populates the parameter treeview with compiled
        params and flattened metadata."""
        for i in self.tree_params.get_children():
            self.tree_params.delete(i)
        params = entry_data.get("compiled_params", [])
        for p in params:
            flag = p.get("flag", "")
            val = p.get("value", "")
            cmd = self.cmd_loader.get_by_flag(flag)
            name = cmd["name"] if cmd else flag
            self.tree_params.insert("", "end", values=(name, val))
        meta = entry_data.get("metadata", {})
        if "seed" in meta:
            self.tree_params.insert(
                "", "end", values=(i18n.get("history.extra.seed"), meta["seed"])
            )
        if "time_ms" in meta:
            self.tree_params.insert(
                "",
                "end",
                values=(i18n.get("history.extra.time"), meta["time_ms"]),
            )
        if "command" in meta:
            self.tree_params.insert(
                "",
                "end",
                values=(i18n.get("history.extra.command"), meta["command"]),
            )
        handled_meta = {"seed", "time_ms", "command"}

        def _flatten(d: Dict[str, Any], parent: str = "") -> None:
            for k, v in d.items():
                full_key = f"{parent}.{k}" if parent else k
                if parent == "" and k in handled_meta:
                    continue
                if isinstance(v, dict):
                    _flatten(v, full_key)
                else:
                    self.tree_params.insert(
                        "", "end", values=(full_key, str(v))
                    )

        _flatten(meta)
        ignored_top = {"compiled_params", "metadata", "prompt", "output_path"}
        for k, v in entry_data.items():
            if k not in ignored_top:
                self.tree_params.insert("", "end", values=(k, str(v)))

    def _show_details_meta(self, entry_data: HistoryData) -> None:
        """Logic: Formats and displays the raw entry data as JSON."""
        self.txt_meta.configure(state="normal")
        self.txt_meta.delete("1.0", "end")
        formatted_json = json.dumps(entry_data, indent=4, ensure_ascii=False)
        self.txt_meta.insert("1.0", formatted_json)
        self.txt_meta.configure(state="disabled")

    def clear_view(self) -> None:
        """Resets the detail panel to its initial state.

        Logic: Clears image, text fields, treeview, and disables buttons."""
        self.lbl_big_img.configure(
            image=None, text=i18n.get("history.msg.select_image")
        )
        self.txt_prompt.delete("1.0", "end")
        self.btn_restore.configure(state="disabled")
        self.btn_copy.configure(state="disabled")
        for i in self.tree_params.get_children():
            self.tree_params.delete(i)
        self.txt_meta.configure(state="normal")
        self.txt_meta.delete("1.0", "end")
        self.txt_meta.configure(state="disabled")
