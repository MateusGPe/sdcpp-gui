from __future__ import annotations

import threading
import tkinter as tk
from tkinter import BOTH, HORIZONTAL, LEFT, RIGHT, X, messagebox
from typing import TYPE_CHECKING, List

import ttkbootstrap as ttk

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.data.remote.civitai_client import KNOWN_BASE_MODELS
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.plugins.core_remote.components.model_card import ModelCard
from sd_cpp_gui.plugins.core_remote.panels.details import DetailsPanel
from sd_cpp_gui.ui.components import entry, flat
from sd_cpp_gui.ui.components.scroll_frame import SmoothScrollFrame
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.data.remote.types import RemoteModelDTO
    from sd_cpp_gui.infrastructure.i18n import I18nManager
    from sd_cpp_gui.plugins.core_remote.window import (
        RemoteBrowserWindow,
    )

i18n: I18nManager = get_i18n()


class SearchTab(ttk.Frame):
    def __init__(
        self, parent: tk.Widget, controller: RemoteBrowserWindow
    ) -> None:
        """Logic: Initializes search variables and builds UI."""
        super().__init__(parent)
        self.controller = controller
        self.search_query = tk.StringVar()
        self.filter_type = tk.StringVar(value="Checkpoint")
        self.filter_base = tk.StringVar(value="All")
        self.filter_sort = tk.StringVar(value="Highest Rated")
        self.filter_period = tk.StringVar(value="AllTime")
        self.is_nsfw = tk.BooleanVar(value=False)
        self.current_page = 1
        self._init_ui()

    def _init_ui(self) -> None:
        """Logic: Creates API warning, Search bar, Pagination, Filters,
        and Split view (Results + Details)."""
        self.api_warning_frame = ttk.Frame(self, bootstyle="warning", padding=2)
        lbl = CopyLabel(
            self.api_warning_frame,
            text=i18n.get(
                "remote.search.warn_api",
                "⚠️ No Civitai API Key. NSFW/Downloads restricted.",
            ),
            bootstyle="inverse-warning",
            font=(SYSTEM_FONT, 8, "bold"),
        )
        lbl.pack(side=LEFT, padx=5)
        flat.RoundedButton(
            self.api_warning_frame,
            text=i18n.get("remote.search.btn_fix", "Fix"),
            width=50,
            height=20,
            command=lambda: self.controller.notebook.select(
                self.controller.tab_config
            ),
            bootstyle="light",
        ).pack(side=LEFT)
        header = ttk.Frame(self, padding=(5, 5, 5, 0))
        header.pack(fill=X)
        row1 = ttk.Frame(header)
        row1.pack(fill=X, pady=(0, 5))
        self.entry_search = entry.MEntry(
            row1,
            textvariable=self.search_query,
            height=36,
            elevation=1,
            radius=CORNER_RADIUS,
        )
        self.entry_search.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        self.entry_search.bind("<Return>", lambda e: self._do_search())
        flat.RoundedButton(
            row1,
            text=i18n.get("remote.tab.search", "Search"),
            command=self._do_search,
            bootstyle="primary",
            corner_radius=CORNER_RADIUS,
            elevation=1,
            width=100,
            height=36,
        ).pack(side=LEFT, padx=(0, 10))
        self._build_pagination(row1)
        self._build_filters_compact(header)
        ttk.Separator(self, orient=HORIZONTAL).pack(fill=X, pady=(5, 5))
        paned = ttk.Panedwindow(self, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=5, pady=(0, 5))
        self.results_frame = SmoothScrollFrame(paned, bootstyle="bg")
        paned.add(self.results_frame, weight=3)
        details_wrapper = ttk.Frame(paned)
        self.details_scroll = SmoothScrollFrame(details_wrapper)
        self.details_scroll.pack(fill=BOTH, expand=True)
        self.details_content = DetailsPanel(
            self.details_scroll.content, self.controller
        )
        self.details_content.pack(fill=BOTH, expand=True, padx=5, pady=5)
        paned.add(details_wrapper, weight=2)

    def _build_pagination(self, parent: ttk.Frame) -> None:
        """Logic: Adds Prev/Next buttons and page label."""
        flat.RoundedButton(
            parent,
            text="<",
            width=32,
            height=32,
            elevation=1,
            command=self._prev_page,
            bootstyle="secondary",
            corner_radius=14,
        ).pack(side=LEFT)
        self.lbl_page = CopyLabel(
            parent,
            text="1",
            width=3,
            anchor="center",
            font=(SYSTEM_FONT, 9, "bold"),
        )
        self.lbl_page.pack(side=LEFT, padx=2)
        flat.RoundedButton(
            parent,
            text=">",
            width=32,
            height=32,
            elevation=1,
            command=self._next_page,
            bootstyle="secondary-outline",
            corner_radius=14,
        ).pack(side=LEFT)

    def _build_filters_compact(self, parent: ttk.Frame) -> None:
        """Horizontal filter layout: Label | Combo | Label | Combo

        Logic: Creates compact row of filters (Type, Base, Sort, Time, NSFW)."""
        row2 = ttk.Frame(parent)
        row2.pack(fill=X, pady=0)

        def add_filter(label, var, values, width=12):
            f = ttk.Frame(row2)
            f.pack(side=LEFT, padx=(0, 10))
            CopyLabel(f, text=label, font=(SYSTEM_FONT, 8)).pack(
                side=LEFT, padx=(0, 4)
            )
            cb = ttk.Combobox(
                f,
                textvariable=var,
                values=values,
                state="readonly",
                width=width,
                font=(SYSTEM_FONT, 8),
            )
            cb.pack(side=LEFT)
            cb.bind("<<ComboboxSelected>>", lambda e: self._do_search())

        add_filter(
            i18n.get("remote.search.lbl_type", "Type:"),
            self.filter_type,
            ["Checkpoint", "LoRA", "Embedding", "ControlNet"],
            width=10,
        )
        add_filter("Base:", self.filter_base, KNOWN_BASE_MODELS, width=11)
        add_filter(
            i18n.get("remote.search.lbl_base", "Base:"),
            self.filter_base,
            KNOWN_BASE_MODELS,
            width=11,
        )
        add_filter(
            i18n.get("remote.search.lbl_sort", "Sort:"),
            self.filter_sort,
            ["Highest Rated", "Most Downloaded", "Newest"],
            width=14,
        )
        add_filter(
            i18n.get("remote.search.lbl_time", "Time:"),
            self.filter_period,
            ["AllTime", "Year", "Month", "Week", "Day"],
            width=8,
        )
        tgl = ttk.Checkbutton(
            row2,
            text=i18n.get("remote.search.chk_nsfw", "NSFW"),
            variable=self.is_nsfw,
            bootstyle="round-toggle",
            command=self._do_search,
        )
        tgl.pack(side=RIGHT)

    def toggle_api_warning(self, visible: bool) -> None:
        """Logic: Shows or hides the missing API key warning."""
        if visible:
            self.api_warning_frame.pack(
                fill=X, before=self.entry_search.master.master, pady=(0, 2)
            )
        else:
            self.api_warning_frame.pack_forget()

    def _prev_page(self) -> None:
        """Logic: Decrements page and searches."""
        if self.current_page > 1:
            self.current_page -= 1
            self._do_search(reset_page=False)

    def _next_page(self) -> None:
        """Logic: Increments page and searches."""
        self.current_page += 1
        self._do_search(reset_page=False)

    def _do_search(self, reset_page: bool = True) -> None:
        """Logic: Clears results, starts search thread."""
        if reset_page:
            self.current_page = 1
        self.lbl_page.configure(text=str(self.current_page))
        for w in self.results_frame.content.winfo_children():
            w.destroy()
        self.controller.status_bar.configure(
            text=i18n.get("remote.search.status_searching", "Searching..."),
            bootstyle="info",
        )
        threading.Thread(target=self._search_worker, daemon=True).start()

    def _search_worker(self) -> None:
        """Logic: Executes remote search query and schedules
        result rendering."""
        try:
            repo = self.controller.remote.get_repository(
                self.controller.current_provider
            )
            res = repo.search_models(
                self.search_query.get(),
                self.filter_type.get(),
                base_model=self.filter_base.get(),
                page=self.current_page,
                nsfw=self.is_nsfw.get(),
            )
            self.after(0, lambda: self._render_results(res))
        except Exception as e:
            self.after(0, lambda e=e: self._show_search_error(str(e)))

    def _show_search_error(self, msg: str) -> None:
        """Logic: Displays search error in status bar and message box."""
        self.controller.status_bar.configure(
            text=f"Error: {msg}", bootstyle="danger"
        )
        messagebox.showerror(
            i18n.get("remote.search.error_title", "Search Failed"),
            msg,
            parent=self,
        )

    def _render_results(self, results: List[RemoteModelDTO]) -> None:
        """Logic: Creates Grid of ModelCards from search results and
        updates status."""
        if not results:
            self.controller.status_bar.configure(
                text=i18n.get(
                    "remote.search.status_no_results", "No results found."
                ),
                bootstyle="warning",
            )
            return

        status_msg = i18n.get(
            "remote.search.status_found", "Found {count} models."
        ).format(count=len(results))
        self.controller.status_bar.configure(
            text=status_msg, bootstyle="success"
        )
        self.controller.ownership.refresh()
        m_type = self.filter_type.get()
        cols = 3
        width = self.winfo_width()
        if width > 1400:
            cols = 4
        elif width < 900:
            cols = 2
        for i, item in enumerate(results):
            r, c = divmod(i, cols)
            owned_count = 0
            for v in item.get("versions", []):
                if self.controller.ownership.check_version(m_type, v["id"]):
                    owned_count += 1
            card = ModelCard(
                self.results_frame.content,
                item,
                self.details_content.load_model,
                self.controller.img_loader,
                owned_versions=owned_count,
            )
            card.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
        for i in range(cols):
            self.results_frame.content.columnconfigure(i, weight=1)
