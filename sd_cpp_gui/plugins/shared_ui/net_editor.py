"""
LoRA Library Management Window.
Refactored to use a Master-Detail (Treeview + Form) layout.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import BOTH, BOTTOM, END, LEFT, RIGHT, X
from ttkbootstrap.widgets import ToolTip
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from sd_cpp_gui.constants import CORNER_RADIUS, EMOJI_FONT, SYSTEM_FONT
from sd_cpp_gui.data.db.models import LoraData
from sd_cpp_gui.data.remote.civitai_client import KNOWN_BASE_MODELS
from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components import entry, flat, text
from sd_cpp_gui.ui.components.thumb_view import (
    LazzyThumbView,
    ThumbProps,
    ThumbViewConfig,
)
from sd_cpp_gui.ui.components.utils import CopyLabel

i18n: I18nManager = get_i18n()
logger = get_logger(__name__)


class NetworkEditor(ttk.Toplevel):
    """
    Modal window for managing the LoRA Library.
    Layout: Split Pane (Left: Treeview, Right: Editor Form).
    """

    def __init__(
        self,
        parent: tk.Misc,
        lora_manager: Any,
        on_close_callback: Callable[[], None],
        network_type: str = "lora",
    ) -> None:
        """Logic: Initializes window, sets title based on type
        (LoRA/Embedding), sets up layout and variables."""
        super().__init__(master=parent)
        self.network_type = network_type
        self._set_window_title()
        self.geometry("900x600")
        self.transient(master=parent)
        self.manager = lora_manager
        self.on_close_callback = on_close_callback
        self.current_lora_data: Optional[LoraData] = None
        self.var_filename = ttk.StringVar()
        self.var_path = ttk.StringVar()
        self.var_alias = ttk.StringVar()
        self.var_strength = ttk.DoubleVar(value=1.0)
        self.var_search = ttk.StringVar()
        self._image_cache: Dict[str, Image.Image] = {}
        self._edit_controls: List[tk.Widget] = []
        self.entry_filename: Optional[entry.MEntry] = None
        self.entry_path: Optional[entry.MEntry] = None
        self._preview_image_ref = None
        self._init_ui()
        self._refresh_list()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _set_window_title(self) -> None:
        """Logic: Sets window title appropriate for the network type."""
        if self.network_type == "embedding":
            self.title(
                i18n.get("embedding.window.title", "Embedding Library Manager")
            )
        else:
            self.title(i18n.get("lora.window.title", "LoRA Library Manager"))

    def _init_ui(self) -> None:
        """Logic: Builds the main UI: Toolbar, Split Pane (Tree + Form),
        and Footer."""
        main_container = ttk.Frame(self, padding=8)
        main_container.pack(fill=BOTH, expand=True)
        self._init_toolbar(main_container)
        self.paned = ttk.Panedwindow(main_container, orient="horizontal")
        self.paned.pack(fill=BOTH, expand=True, pady=8)
        left_frame = ttk.Frame(self.paned, width=300)
        self._init_left_pane(left_frame)
        self.paned.add(left_frame, weight=1)
        right_frame = ttk.Frame(self.paned)
        self._init_right_pane(right_frame)
        self.paned.add(right_frame, weight=2)

    def _init_toolbar(self, parent: ttk.Frame) -> None:
        """Logic: Creates toolbar with Refresh, Scan, and Search widgets."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=X, pady=(0, 8))
        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side=RIGHT)
        flat.RoundedButton(
            btn_frame,
            text="🔄 Refresh",
            bootstyle="info",
            width=120,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=self._refresh_libraries,
        ).pack(side=LEFT)
        flat.RoundedButton(
            btn_frame,
            text=i18n.get("system.btn.import", "Scan New Folder"),
            bootstyle="success",
            width=120,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=self._import_folder,
        ).pack(side=LEFT)
        flat.RoundedButton(
            btn_frame,
            text=i18n.get("lora.btn.close", "Close"),
            bootstyle="warning",
            width=80,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=self._close,
        ).pack(side=RIGHT)
        e_search = entry.MEntry(
            toolbar,
            textvariable=self.var_search,
            bootstyle="secondary",
            height=32,
            radius=CORNER_RADIUS,
        )
        e_search.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        e_search.bind("<KeyRelease>", self._on_search)
        ToolTip(e_search, text="Filter by name...", bootstyle="secondary")
        lbl_icon = tk.Label(e_search.canvas, text="🔍", font=(EMOJI_FONT, 10))
        icon_window = e_search.canvas.create_window(
            0, 0, window=lbl_icon, anchor="center", tags="search_icon"
        )

        def _reposition_icon(e: tk.Event) -> None:
            if not e.widget.winfo_exists():
                return
            current_colors = e_search.color_manager.update_palette()
            lbl_icon.configure(background=current_colors["bg"])
            x_pos = e.width - e_search.padding * 1.8
            y_pos = e.height / 2
            e.widget.coords(icon_window, x_pos, y_pos)

        e_search.canvas.bind("<Configure>", _reposition_icon, add="+")

    def _init_left_pane(self, parent: ttk.Frame) -> None:
        """Logic: Creates the Treeview for listing folders and items."""
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
            parent,
            config=cfg,
            image_loader=self._cached_image_loader,
            on_selection_changed=self._on_selection_changed,
        )
        self.thumb_view.pack(fill=BOTH, expand=True)

    def _init_right_pane(self, parent: ttk.Frame) -> None:
        """Logic: Creates the detail form with fields for Filename, Path,
        Base Model, Alias, Strength, Triggers, and Action buttons."""
        self.form_frame = ScrolledFrame(parent, padding=(0, 0, 20, 0))
        self.form_frame.pack(fill=BOTH, expand=True, padx=(10, 0))

        self.preview_container = ttk.Frame(self.form_frame)
        self.preview_container.pack(fill=X, pady=(0, 10))
        self.lbl_preview = CopyLabel(
            self.preview_container,
            text="Select an item to view details",
            anchor="center",
            bootstyle="secondary",
        )
        self.lbl_preview.pack(fill=BOTH, expand=True)

        info_grid = ttk.Frame(self.form_frame)
        info_grid.pack(fill=X, pady=(0, 8))
        info_grid.columnconfigure(1, weight=1)
        CopyLabel(
            info_grid,
            text="Filename:",
            font=(SYSTEM_FONT, 8, "bold"),
            bootstyle="secondary",
        ).grid(row=0, column=0, sticky="w")
        self.entry_filename = entry.MEntry(
            info_grid,
            textvariable=self.var_filename,
            state="readonly",
            bootstyle="secondary",
        )
        self.entry_filename.grid(row=0, column=1, sticky="ew", padx=5)
        CopyLabel(
            info_grid,
            text="Full Path:",
            font=(SYSTEM_FONT, 8, "bold"),
            bootstyle="secondary",
        ).grid(row=1, column=0, sticky="w", pady=5)
        self.entry_path = entry.MEntry(
            info_grid,
            textvariable=self.var_path,
            state="readonly",
            bootstyle="secondary",
        )
        self.entry_path.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Separator(self.form_frame, orient="horizontal").pack(fill=X, pady=8)
        CopyLabel(
            info_grid,
            text="Base Model:",
            font=(SYSTEM_FONT, 8, "bold"),
            bootstyle="secondary",
        ).grid(row=2, column=0, sticky="w", pady=5)
        self.var_base_model = ttk.StringVar()
        self.cb_base_model = ttk.Combobox(
            info_grid,
            textvariable=self.var_base_model,
            values=KNOWN_BASE_MODELS,
            state="readonly",
        )
        self.cb_base_model.grid(row=2, column=1, sticky="ew", padx=5)
        CopyLabel(
            self.form_frame,
            text=i18n.get("lora.col.alias", "Alias Name"),
            font=(SYSTEM_FONT, 10, "bold"),
        ).pack(anchor="w")
        self.e_alias = entry.MEntry(
            self.form_frame, textvariable=self.var_alias, radius=CORNER_RADIUS
        )
        self.e_alias.pack(fill=X, pady=(5, 8))
        CopyLabel(
            self.form_frame,
            text=i18n.get("lora.col.strength", "Default Strength"),
            font=(SYSTEM_FONT, 10, "bold"),
        ).pack(anchor="w")
        f_str = ttk.Frame(self.form_frame)
        f_str.pack(fill=X, pady=(5, 8))
        self.scale_strength = ttk.Scale(
            f_str,
            from_=-2.0,
            to=2.0,
            variable=self.var_strength,
            command=lambda v: self.var_strength.set(round(float(v), 2)),
        )
        self.scale_strength.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.e_strength = entry.MEntry(
            f_str,
            textvariable=self.var_strength,
            width=60,
            radius=CORNER_RADIUS,
        )
        self.e_strength.pack(side=RIGHT)
        CopyLabel(
            self.form_frame,
            text=i18n.get(
                "lora.col.triggers", "Trigger Words (comma separated)"
            ),
            font=(SYSTEM_FONT, 10, "bold"),
        ).pack(anchor="w")
        self.txt_triggers = text.MText(
            self.form_frame, height=80, font=(SYSTEM_FONT, 9), wrap="word"
        )
        self.txt_triggers.pack(fill=BOTH, expand=True, pady=(5, 15))
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=X, side=BOTTOM)
        self.btn_save = flat.RoundedButton(
            btn_row,
            text=i18n.get("editor.btn.save", "💾 Save Changes"),
            bootstyle="primary",
            width=140,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=self._save_changes,
        )
        self.btn_save.pack(side=RIGHT)
        self.btn_delete = flat.RoundedButton(
            btn_row,
            text=i18n.get("general.btn.delete", "🗑️ Delete"),
            bootstyle="danger",
            width=100,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=self._delete_item,
        )
        self.btn_delete.pack(side=LEFT)
        self._edit_controls = [
            self.e_alias,
            self.scale_strength,
            self.e_strength,
            self.txt_triggers,
            self.btn_save,
            self.btn_delete,
        ]
        self._toggle_form(False)

    def _toggle_form(self, enabled: bool) -> None:
        """Logic: Enables or disables form widgets based on whether an
        item is selected."""
        state = "normal" if enabled else "disabled"
        ro_state = "readonly" if enabled else "disabled"
        if self.entry_filename:
            self.entry_filename.configure(state=ro_state)
        if self.entry_path:
            self.entry_path.configure(state=ro_state)
        for widget in self._edit_controls:
            widget.configure(state=state)
        if not enabled:
            self.var_filename.set("")
            self.var_path.set("")
            self.var_alias.set("")
            self.var_strength.set(1.0)
            self.txt_triggers.delete("1.0", END)
            self.lbl_preview.configure(
                image="", text="Select an item to view details"
            )

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

    def _refresh_list(self) -> None:
        """Rebuilds the treeview from the manager's data.

        Logic: Rebuilds the treeview hierarchy from the manager's data,
        applying search filter if present."""
        folders = self.manager.get_known_folders()
        search_q = self.var_search.get().lower()
        props_list = []

        for folder in folders:
            items = self.manager.get_by_folder(folder)
            for item in items:
                name = item.get("name", "Unknown")
                alias = item.get("alias", "")
                if search_q and (
                    search_q not in name.lower()
                    and search_q not in alias.lower()
                ):
                    continue
                display_text = alias if alias else name
                preview_path = self._find_preview_path(item.get("path"))
                props = ThumbProps(
                    id=item["id"],
                    image_path=preview_path,
                    description=display_text,
                    data=item,
                )
                props_list.append(props)

        self.thumb_view.set_items(props_list)

    def _on_search(self, _event: tk.Event) -> None:
        """Logic: Triggers tree refresh when search text changes."""
        self._refresh_list()

    def _on_selection_changed(self, selected_items: List[ThumbProps]) -> None:
        """Logic: Handles item selection: loads data into form if
        item is valid, else disables form."""
        if not selected_items:
            self._toggle_form(False)
            self.current_lora_data = None
            return

        data = selected_items[-1].data
        self.current_lora_data = data
        self._toggle_form(True)
        self._load_form(data)

    def _load_preview(self, model_path: str) -> None:
        """Logic: Loads and displays the preview image for the selected model.
        Resizes the image to fit the preview area (max height 200px)."""
        preview_path = self._find_preview_path(model_path)

        if preview_path:
            try:
                pil_img = Image.open(preview_path)

                target_h = 200
                h_ratio = target_h / float(pil_img.size[1])
                target_w = int(float(pil_img.size[0]) * float(h_ratio))

                if target_w > 400:
                    target_w = 400
                    target_h = int(
                        target_w / (pil_img.size[0] / pil_img.size[1])
                    )

                pil_img = pil_img.resize(
                    (target_w, target_h), Image.Resampling.LANCZOS
                )
                self._preview_image_ref = ImageTk.PhotoImage(pil_img)
                self.lbl_preview.configure(
                    image=self._preview_image_ref, text=""
                )
            except Exception as e:
                logger.error(f"Error loading preview: {e}")
                self.lbl_preview.configure(image="", text="Preview Error")
        else:
            self.lbl_preview.configure(image="", text="No Preview Image Found")

    def _load_form(self, data: LoraData) -> None:
        """Logic: Populates form fields with data from the selected item."""
        self.var_filename.set(data.get("filename", ""))
        self.var_path.set(data.get("path", ""))
        self.var_alias.set(data.get("alias", ""))
        self.var_strength.set(data.get("preferred_strength", 1.0))
        self.var_base_model.set(data.get("base_model") or "")
        self.txt_triggers.delete("1.0", END)
        triggers = data.get("trigger_words", "")
        if triggers:
            self.txt_triggers.insert("1.0", triggers)
        self._load_preview(data.get("path", ""))

    def _save_changes(self) -> None:
        """Logic: Collects form data, updates the item via manager,
        refreshes tree, and shows success message."""
        if not self.current_lora_data:
            return
        current_id = self.current_lora_data["id"]
        new_alias = self.var_alias.get().strip()
        new_base = self.var_base_model.get()
        try:
            new_str = float(self.var_strength.get())
        except ValueError:
            new_str = 1.0
        new_triggers = (
            self.txt_triggers.get("1.0", END).strip().replace("\n", ", ")
        )
        if self.network_type == "embedding":
            self.manager.update_embedding_metadata(
                current_id, new_alias, new_str, new_triggers
            )
        else:
            self.manager.update_lora_metadata(
                current_id, new_alias, new_str, new_triggers, new_base
            )
        self._refresh_list()

        # Restore selection
        if current_id in self.thumb_view._all_items_map:
            self.thumb_view._selected_ids.add(current_id)
            self.thumb_view._update_visuals()
            self.thumb_view._trigger_selection()

        messagebox.showinfo("Saved", "Metadata updated successfully.")

    def _delete_item(self) -> None:
        """Logic: Prompts for confirmation and deletes the selected
        item from the library (DB only)."""
        if not self.current_lora_data:
            return
        name = self.var_alias.get() or self.var_filename.get()
        if messagebox.askyesno(
            "Confirm Delete",
            f"Remove '{name}' from library?\n"
            "(This does not delete the actual file)",
        ):
            if self.network_type == "embedding":
                self.manager.delete_embedding(self.current_lora_data["id"])
            else:
                self.manager.delete_lora(self.current_lora_data["id"])
            self.current_lora_data = None
            self._toggle_form(False)
            self._refresh_list()

    def _import_folder(self) -> None:
        """Logic: Opens folder dialog, scans for new files, imports them,
        and refreshes the tree."""
        folder = filedialog.askdirectory(parent=self)
        if folder:
            count = self.manager.scan_and_import_folder(folder)
            messagebox.showinfo("Scan Complete", f"Found {count} new items.")
            self._refresh_list()

    def _refresh_libraries(self) -> None:
        """Rescans all known folders to sync missing/new files.

        Logic: Syncs all known folders, reports added/removed counts,
        and refreshes the tree."""
        folders = self.manager.get_known_folders()
        total_added = 0
        total_removed = 0
        for folder in folders:
            stats = self.manager.sync_folder(folder)
            total_added += stats["added"]
            total_removed += stats["removed"]
        self._refresh_list()
        messagebox.showinfo(
            "Library Refresh",
            f"Sync Complete:\n➕ {total_added} new items added.\n"
            f"➖ {total_removed} missing items removed.",
        )

    def _close(self) -> None:
        """Logic: Executes callback and destroys the window."""
        self.on_close_callback()
        self.destroy()
