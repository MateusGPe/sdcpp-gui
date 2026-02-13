"""
History Window Module.
"""

from __future__ import annotations

import math
import os
import threading
import tkinter as tk
from queue import Queue
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import BOTH, BOTTOM, HORIZONTAL, LEFT, RIGHT, X

from sd_cpp_gui.constants import CORNER_RADIUS, EMOJI_FONT, SYSTEM_FONT
from sd_cpp_gui.data.db.models import HistoryData
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import entry, flat
from sd_cpp_gui.ui.components.scroll_frame import SmoothScrollFrame
from sd_cpp_gui.ui.components.utils import CopyLabel, center_window
from sd_cpp_gui.ui.features.history.detail_panel import HistoryDetailPanel

if TYPE_CHECKING:
    from sd_cpp_gui.data.db.data_manager import HistoryManager, ModelManager
    from sd_cpp_gui.domain.generation.commands_loader import CommandLoader
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()
THUMBNAIL_SIZE = (60, 60)


class HistoryItemWidget(ttk.Frame):
    """
    An individual 'Card' in the left-side list.
    """

    # pylint: disable=too-many-ancestors
    def __init__(
        self,
        parent: ttk.Frame,
        entry_data: HistoryData,
        model_name: str,
        select_callback: Callable[[HistoryItemWidget], None],
    ) -> None:
        """Logic: Creates a card displaying thumbnail placeholder,
        model name, date, and truncated prompt."""
        super().__init__(parent, bootstyle="bg", padding=(10, 8))
        self.entry = entry_data
        self.select_callback = select_callback
        self.columnconfigure(1, weight=1)
        self.lbl_thumb = CopyLabel(
            self,
            text="📷",
            width=6,
            anchor="center",
            font=(EMOJI_FONT, 14),
            bootstyle="secondary-inverse",
        )
        self.lbl_thumb.grid(
            row=0, column=0, rowspan=3, padx=(0, 12), sticky="ns"
        )
        display_name = (
            model_name if len(model_name) < 25 else model_name[:22] + "..."
        )
        self.lbl_model = CopyLabel(
            self, text=display_name, font=(SYSTEM_FONT, 10, "bold"), anchor="w"
        )
        self.lbl_model.grid(row=0, column=1, sticky="w")
        ts = entry_data.get("timestamp", "--/-- --:--")
        self.lbl_date = CopyLabel(
            self, text=ts, font=(SYSTEM_FONT, 8), bootstyle="secondary"
        )
        self.lbl_date.grid(row=1, column=1, sticky="w", pady=(0, 4))
        raw_p = entry_data.get("prompt", "").replace("\n", " ")
        short_p = raw_p[:45] + "..." if len(raw_p) > 45 else raw_p
        self.lbl_prompt = CopyLabel(
            self,
            text=short_p,
            font=(SYSTEM_FONT, 9, "italic"),
            bootstyle="secondary",
        )
        self.lbl_prompt.grid(row=2, column=1, sticky="w")
        for widget in [
            self,
            self.lbl_thumb,
            self.lbl_model,
            self.lbl_date,
            self.lbl_prompt,
        ]:
            widget.bind("<Button-1>", self._on_click)

    def _on_click(self, event: tk.Event) -> None:
        """Logic: Triggers the selection callback."""
        self.select_callback(self)

    def set_selected(self, is_selected: bool) -> None:
        """Toggles visual between Normal (Clean) and Selected (Highlight).

        Logic: Updates background and text colors
        to indicate selection state."""
        if is_selected:
            bg_style = "primary"
            self.lbl_model.configure(bootstyle="inverse-primary")
            self.lbl_date.configure(bootstyle="inverse-primary")
            self.lbl_prompt.configure(bootstyle="inverse-primary")
        else:
            bg_style = "bg"
            self.lbl_model.configure(bootstyle="default")
            self.lbl_date.configure(bootstyle="secondary")
            self.lbl_prompt.configure(bootstyle="secondary")
        self.configure(bootstyle=bg_style)

    def update_thumbnail(self, tk_img: ImageTk.PhotoImage) -> None:
        """Updates the placeholder with the real image (called via thread).

        Logic: Updates the image label if widget exists."""
        if self.winfo_exists():
            self.lbl_thumb.configure(image=tk_img, text="", bootstyle="")
            self.lbl_thumb.image = tk_img  # type: ignore


class HistoryWindow(ttk.Toplevel):
    """Complete History Window."""

    # pylint: disable=too-many-ancestors,too-many-instance-attributes
    def __init__(
        self,
        parent: ttk.Window,
        history_manager: HistoryManager,
        model_manager: ModelManager,
        cmd_loader: CommandLoader,
        load_callback: Callable[[str], None],
    ) -> None:
        """Logic: Initializes window, managers, queues,
        builds UI, and starts data loading."""
        super().__init__(master=parent)
        self.title(i18n.get("history.window.title"))
        self.geometry("1200x800")
        self.transient(parent)
        self.history = history_manager
        self.models = model_manager
        self.cmd_loader = cmd_loader
        self.load_callback = load_callback
        self.full_data: List[HistoryData] = []
        self.model_map: Dict[str, str] = {}
        self.item_widgets: List[HistoryItemWidget] = []
        self.selected_widget: Optional[HistoryItemWidget] = None
        self.var_search = tk.StringVar()
        self.var_model_filter = tk.StringVar()
        self._search_job: Optional[str] = None
        self.current_page = 1
        self.page_size = 10
        self.total_pages = 1
        self.paned: ttk.Panedwindow
        self.list_container: ttk.Frame
        self.scrolled_list: SmoothScrollFrame
        self.detail_panel: HistoryDetailPanel
        self.entry_search: entry.MEntry
        self.cb_models: ttk.Combobox
        self.stop_thread = False
        self.thread_queue: Queue[Optional[Tuple[HistoryItemWidget, str]]] = (
            Queue()
        )
        center_window(self, parent, 1200, 800)
        self._build_model_map()
        self._init_ui()
        self._load_data()

    def destroy(self) -> None:
        """Stops the image thread when the window is closed.

        Logic: Signals image loader thread to stop and calls super destroy."""
        self.stop_thread = True
        self.thread_queue.put(None)
        super().destroy()

    def _build_model_map(self) -> None:
        """Creates an ID -> Model Name map for quick display.

        Logic: Creates a dictionary mapping model IDs
        to names for UI display."""
        all_models = self.models.get_all()
        self.model_map = {m["id"]: m["name"] for m in all_models}

    def _init_ui(self) -> None:
        """Logic: Builds Layout: Header with filters, Split pane
        (List + Detail), and Pagination."""
        header = ttk.Frame(self, padding=10)
        header.pack(fill=X)
        CopyLabel(
            header, text=i18n.get("btn.history"), font=(SYSTEM_FONT, 14, "bold")
        ).pack(side=LEFT)
        f_filters = ttk.Frame(header)
        f_filters.pack(side=RIGHT)
        CopyLabel(
            f_filters,
            text=i18n.get("history.filter.label"),
            font=(SYSTEM_FONT, 9),
        ).pack(side=LEFT, padx=(0, 5))
        self.entry_search = entry.MEntry(
            f_filters,
            textvariable=self.var_search,
            width=180,
            elevation=1,
            bootstyle="secondary",
        )
        self.entry_search.pack(side=LEFT, padx=5)
        self.entry_search.bind("<KeyRelease>", self._on_search)
        self.cb_models = ttk.Combobox(
            f_filters,
            textvariable=self.var_model_filter,
            state="readonly",
            width=20,
        )
        self.cb_models.pack(side=LEFT, padx=5)
        self.cb_models.bind("<<ComboboxSelected>>", self._on_search)
        flat.RoundedButton(
            f_filters,
            text="🧹",
            width=50,
            height=50,
            corner_radius=CORNER_RADIUS,
            bootstyle="secondary",
            command=self._clear_filters,
        ).pack(side=LEFT)
        self.paned = ttk.Panedwindow(self, orient=HORIZONTAL)
        self.paned.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.list_container = ttk.Frame(self.paned, width=380)
        self.paned.add(self.list_container, weight=0)
        self.scrolled_list = SmoothScrollFrame(
            self.list_container, bootstyle="bg"
        )
        self.scrolled_list.pack(fill=BOTH, expand=True)
        p_frame = ttk.Frame(self.list_container, padding=5, bootstyle="bg")
        p_frame.pack(fill=X, side=BOTTOM)
        self.btn_prev = flat.RoundedButton(
            p_frame,
            text="<",
            command=self._prev_page,
            width=40,
            bootstyle="secondary",
        )
        self.btn_prev.pack(side=LEFT)
        self.lbl_page = CopyLabel(
            p_frame, text="1 / 1", anchor="center", font=(SYSTEM_FONT, 9)
        )
        self.lbl_page.pack(side=LEFT, fill=X, expand=True)
        self.btn_next = flat.RoundedButton(
            p_frame,
            text=">",
            command=self._next_page,
            width=40,
            bootstyle="secondary",
        )
        self.btn_next.pack(side=RIGHT)
        self.detail_panel = HistoryDetailPanel(
            self.paned, self.cmd_loader, self._restore, self._copy
        )
        self.paned.add(self.detail_panel, weight=3)

    def _load_data(self) -> None:
        """Logic: Populates model filter combobox, loads initial page,
        and starts thumbnail loader thread."""
        used_ids = self.history.get_used_model_ids()
        model_names = sorted(
            list(
                set(
                    self.model_map.get(mid, i18n.get("common.unknown"))
                    for mid in used_ids
                )
            )
        )
        self.cb_models["values"] = model_names
        self._load_page_data()
        threading.Thread(target=self._image_loader_worker, daemon=True).start()

    def _load_page_data(self) -> None:
        """Logic: Clears list, fetches paginated data based on filters,
        creates ItemWidgets, and queues thumbnail loads."""
        for w in self.scrolled_list.content.winfo_children():
            w.destroy()
        self.item_widgets.clear()
        with self.thread_queue.mutex:
            self.thread_queue.queue.clear()
        self.selected_widget = None
        self._clear_detail_view()
        query = self.var_search.get().lower()
        mod_filter_name = self.var_model_filter.get()
        mod_id = None
        if mod_filter_name:
            for mid, mname in self.model_map.items():
                if mname == mod_filter_name:
                    mod_id = mid
                    break
        total_items = self.history.get_count(
            model_id=mod_id, search_query=query
        )
        self.total_pages = math.ceil(total_items / self.page_size) or 1
        self.current_page = max(1, min(self.total_pages, self.current_page))
        self._update_pagination_ui()
        page_data = self.history.get_page(
            page=self.current_page,
            page_size=self.page_size,
            model_id=mod_id,
            search_query=query,
        )
        for item in page_data:
            m_name = self.model_map.get(
                item["model_id"], i18n.get("common.unknown")
            )
            w = HistoryItemWidget(
                self.scrolled_list.content, item, m_name, self._on_item_select
            )
            w.pack(fill=X, pady=0)
            self.item_widgets.append(w)
            paths = item.get("output_path")
            if isinstance(paths, list):
                path = paths[0] if paths else None
            else:
                path = paths
            if path and isinstance(path, str) and os.path.exists(path):
                self.thread_queue.put((w, path))

    def _update_pagination_ui(self) -> None:
        """Logic: Updates page label and button states
        based on current/total pages."""
        self.lbl_page.config(text=f"{self.current_page} / {self.total_pages}")
        self.btn_prev.config(
            state="normal" if self.current_page > 1 else "disabled"
        )
        self.btn_next.config(
            state="normal"
            if self.current_page < self.total_pages
            else "disabled"
        )

    def _prev_page(self) -> None:
        """Logic: Moves to previous page and reloads."""
        if self.current_page > 1:
            self.current_page -= 1
            self._load_page_data()

    def _next_page(self) -> None:
        """Logic: Moves to next page and reloads."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._load_page_data()

    def _image_loader_worker(self) -> None:
        """Background thread to load thumbnails without freezing the UI.

        Logic: Consumes queue to load images, resize them, and schedule UI
        updates safely."""
        while not self.stop_thread:
            item = self.thread_queue.get()
            if item is None:
                break
            widget, path = item
            if not isinstance(path, str):
                continue
            try:
                with Image.open(path) as pil_img:
                    pil_img.thumbnail(THUMBNAIL_SIZE)
                    loaded_img = pil_img.copy()
                if not self.stop_thread:
                    self.after(
                        0,
                        lambda w=widget,
                        img=loaded_img: self._safe_update_thumbnail(w, img),
                    )
            # pylint: disable=broad-exception-caught
            except (IOError, OSError):
                pass
            finally:
                self.thread_queue.task_done()

    def _safe_update_thumbnail(
        self, widget: HistoryItemWidget, pil_img: Image.Image
    ) -> None:
        """Thread-safe method called on main loop to create TkImage.

        Logic: Creates ImageTk from PIL image and updates the widget."""
        if widget.winfo_exists():
            tk_img = ImageTk.PhotoImage(pil_img)
            widget.update_thumbnail(tk_img)

    def _on_item_select(self, widget: HistoryItemWidget) -> None:
        """Logic: Updates selection visual state and shows details
        in detail panel."""
        if self.selected_widget:
            self.selected_widget.set_selected(False)
        self.selected_widget = widget
        widget.set_selected(True)
        self.detail_panel.show_details(widget.entry)

    def _clear_detail_view(self) -> None:
        """Resets the right-side panel.

        Logic: Clears the detail panel."""
        if self.detail_panel:
            self.detail_panel.clear_view()

    def _on_search(self, *args: Any) -> None:
        """Logic: Debounces search input and reloads page data."""
        if self._search_job:
            self.after_cancel(self._search_job)
        self.current_page = 1
        self._search_job = self.after(300, self._load_page_data)

    def _clear_filters(self) -> None:
        """Logic: Resets filters and reloads data."""
        self.var_search.set("")
        self.var_model_filter.set("")
        self.current_page = 1
        self._load_page_data()

    def _restore(self) -> None:
        """Logic: Invokes callback to restore the selected session
        and closes window."""
        if not self.selected_widget:
            return
        uuid = self.selected_widget.entry["uuid"]
        self.load_callback(uuid)
        self.destroy()

    def _copy(self) -> None:
        """Logic: Copies selected item's prompt to clipboard."""
        if self.selected_widget:
            self.clipboard_clear()
            self.clipboard_append(self.selected_widget.entry.get("prompt", ""))
