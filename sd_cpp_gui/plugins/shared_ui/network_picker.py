import os
import threading
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.widgets import ToolTip
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components import entry, flat
from sd_cpp_gui.ui.components.thumb_view import (
    LazzyThumbView,
    ThumbProps,
    ThumbViewConfig,
)
from sd_cpp_gui.ui.components.utils import CopyLabel

logger = get_logger(__name__)


class NetworkPickerDialog(ttk.Toplevel):
    """
    A modal dialog to browse, search, and preview networks (LoRA/Embeddings).
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        items: List[Dict[str, Any]],
        on_select: Callable[[Dict[str, Any]], None],
    ):
        """Logic: Initializes picker dialog."""
        super().__init__(parent)
        self.title(f"Browse {title}")
        self.geometry("950x600")
        self.items = items
        self.on_select = on_select
        self.filtered_items = items
        self._image_cache: Dict[str, Image.Image] = {}
        self._preview_image_ref = None
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + parent.winfo_width() // 2 - 950 // 2
            y = parent.winfo_rooty() + parent.winfo_height() // 2 - 600 // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass
        self._init_ui()
        self._populate_list()

    def _init_ui(self):
        """Logic: Builds UI."""
        toolbar = ttk.Frame(self, padding=10)
        toolbar.pack(fill=tk.X)
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", self._on_search)
        lbl_search = CopyLabel(toolbar, text="🔍", font=(SYSTEM_FONT, 12))
        lbl_search.pack(side=tk.LEFT, padx=(0, 5))
        self.ent_search = entry.MEntry(
            toolbar,
            textvariable=self.var_search,
            width=300,
            radius=CORNER_RADIUS,
            bootstyle="primary",
        )
        self.ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ToolTip(self.ent_search, text="Search by name, alias, or tags...")
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)

        style = ttk.Style()
        colors = style.colors

        cfg = ThumbViewConfig(
            thumb_width=100,
            thumb_height=130,
            show_description=True,
            description_lines=2,
            auto_resize_columns=True,
            bg_color=colors.bg,
            thumb_bg_color=colors.light,
            thumb_border_color=colors.border,
            image_area_bg_color=colors.dark,
            text_color=colors.fg,
            selected_bg_color=colors.primary,
            selected_border_color=colors.primary,
            selected_text_color=colors.selectfg,
            hover_bg_color=colors.secondary,
            hover_border_color=colors.info,
        )

        self.thumb_view = LazzyThumbView(
            left_frame,
            config=cfg,
            image_loader=self._cached_image_loader,
            on_selection_changed=self._on_selection_changed,
            on_item_double_click=self._on_item_double_click,
        )
        self.thumb_view.pack(fill=tk.BOTH, expand=True)

        right_pane = ttk.Frame(paned)
        paned.add(right_pane, weight=1)

        right_frame = ScrolledFrame(right_pane, padding=(10, 0, 20, 0))
        right_frame.pack(fill=tk.BOTH, expand=True)

        self.preview_frame = ttk.Labelframe(
            right_frame, text=" Preview ", bootstyle="secondary"
        )
        self.preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.lbl_preview = CopyLabel(
            self.preview_frame, text="No Preview Available", anchor=tk.CENTER
        )
        self.lbl_preview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.info_frame = ttk.Frame(right_frame)
        self.info_frame.pack(fill=tk.X)
        self.lbl_title = CopyLabel(
            self.info_frame,
            text="Select an item...",
            font=(SYSTEM_FONT, 12, "bold"),
            wraplength=300,
        )
        self.lbl_title.pack(fill=tk.X, anchor=tk.W)
        self.lbl_path = CopyLabel(
            self.info_frame,
            text="",
            font=(SYSTEM_FONT, 8),
            bootstyle="secondary",
            wraplength=300,
        )
        self.lbl_path.pack(fill=tk.X, anchor=tk.W, pady=(0, 5))
        CopyLabel(
            self.info_frame,
            text="Trigger Words:",
            font=(SYSTEM_FONT, 9, "bold"),
        ).pack(anchor=tk.W)
        self.ent_triggers = entry.MEntry(
            self.info_frame, state="readonly", bootstyle="secondary"
        )
        self.ent_triggers.pack(fill=tk.X, pady=2)
        btn_frame = ttk.Frame(right_pane)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        flat.RoundedButton(
            btn_frame,
            text="Add Selected",
            bootstyle="success",
            width=120,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=self._confirm_selection,
        ).pack(side=tk.RIGHT)
        flat.RoundedButton(
            btn_frame,
            text="Cancel",
            bootstyle="secondary",
            width=80,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=self.destroy,
        ).pack(side=tk.RIGHT, padx=5)

    def _cached_image_loader(
        self,
        path: str,
        size: Tuple[int, int],
        callback: Callable[[Optional[Image.Image], bool], None],
    ):
        if path in self._image_cache:
            self.after(0, callback, self._image_cache[path], True)
            return

        def _load():
            try:
                if not path or not os.path.exists(path):
                    self.after(0, callback, None, False)
                    return

                img = Image.open(path)
                img.thumbnail(size, Image.Resampling.LANCZOS)
                self._image_cache[path] = img
                self.after(0, callback, img, True)
            except Exception as e:
                logger.error(f"Error loading {path}: {e}")
                self.after(0, callback, None, False)

        threading.Thread(target=_load, daemon=True).start()

    def _find_preview_path(self, model_path: str) -> Optional[str]:
        if not model_path:
            return None
        base_path = os.path.splitext(model_path)[0]
        for ext in [".preview.png", ".preview.jpg", ".png", ".jpg", ".webp"]:
            candidate = base_path + ext
            if os.path.exists(candidate):
                return candidate
        return None

    def _populate_list(self):
        """Logic: Populates list from items."""
        search = self.var_search.get().lower()
        props_list = []

        for item in self.items:
            name = item.get("alias") or item.get("name", "Unknown")
            filename = item.get("filename", "").lower()
            if search and (
                search not in name.lower() and search not in filename
            ):
                continue

            status = item.get("_compatibility_status")
            display_name = name
            if status == "possible":
                display_name = f"⚠️ {name}"
            elif status == "unknown":
                display_name = f"❓ {name}"

            preview_path = self._find_preview_path(item.get("path"))

            props = ThumbProps(
                id=item["id"],
                image_path=preview_path,
                description=display_name,
                data=item,
            )
            props_list.append(props)

        self.thumb_view.set_items(props_list)

    def _on_search(self, *args):
        """Logic: Filters list on search."""
        self._populate_list()

    def _get_selected_item(self) -> Optional[Dict[str, Any]]:
        """Logic: Gets selected item."""
        selection = self.thumb_view.get_selection()
        if not selection:
            return None
        return selection[0].data

    def _on_selection_changed(self, selected_items: List[ThumbProps]):
        """Logic: Updates preview on focus."""
        if not selected_items:
            return
        item = selected_items[-1].data
        name = item.get("alias") or item.get("name", "Unknown")
        self.lbl_title.configure(text=name)
        self.lbl_path.configure(text=item.get("filename", ""))
        triggers = item.get("trigger_words", "")
        self.ent_triggers.configure(state="normal")
        self.ent_triggers.delete(0, tk.END)
        self.ent_triggers.insert(0, triggers)
        self.ent_triggers.configure(state="readonly")
        self._load_preview(item.get("path"))

    def _load_preview(self, model_path: str):
        """Logic: Loads preview image."""
        preview_path = self._find_preview_path(model_path)
        if preview_path:
            try:
                pil_img = Image.open(preview_path)
                max_w, max_h = (350, 350)
                pil_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                self._preview_image_ref = ImageTk.PhotoImage(pil_img)
                self.lbl_preview.configure(
                    image=self._preview_image_ref, text=""
                )
            except Exception as e:
                self.lbl_preview.configure(
                    image="", text=f"Error loading image\n{e}"
                )
        else:
            self.lbl_preview.configure(
                image="",
                text="No Preview Image Found\n"
                "(Save .preview.png next to model)",
            )

    def _on_item_double_click(self, props: ThumbProps, event):
        """Logic: Confirms selection on double click."""
        self._confirm_selection()

    def _confirm_selection(self):
        """Logic: Confirms selection."""
        item = self._get_selected_item()
        if item:
            self.on_select(item)
            self.destroy()
