"""
Model Editor Module.
Updated to use local StateManager for form handling.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from copy import deepcopy
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypedDict, cast

import ttkbootstrap as ttk
from PIL import Image
from ttkbootstrap.constants import BOTH, BOTTOM, HORIZONTAL, LEFT, RIGHT, X
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.data.db.models import ModelData
from sd_cpp_gui.data.remote.civitai_client import KNOWN_BASE_MODELS
from sd_cpp_gui.domain.generation import GenerationState, StateManager
from sd_cpp_gui.domain.generation.processors import ArgumentProcessor
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components import entry, flat
from sd_cpp_gui.ui.components.thumb_view import (
    LazzyThumbView,
    ThumbProps,
    ThumbViewConfig,
)
from sd_cpp_gui.ui.components.utils import CopyLabel, center_window
from sd_cpp_gui.ui.controls.base import BaseArgumentControl

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()
logger = get_logger(__name__)


class ParamWidgetRow(TypedDict):
    """Defines the widgets that make up a parameter row in the editor."""

    frame: ttk.Frame
    combo: ttk.Combobox
    ctrl_container: ttk.Frame
    ctrl: Optional[BaseArgumentControl]
    delete_btn: tk.Widget


class ModelEditor(ttk.Toplevel):
    """Window for creating/editing model presets."""

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        parent: Any,
        argumentProcessor: ArgumentProcessor,
        model_data: Optional[ModelData] = None,
    ) -> None:
        """Logic: Initializes editor window, local state manager,
        loads data if editing, or defaults if new."""
        super().__init__(parent)
        self.parent = parent
        self.local_state = GenerationState()
        self.local_manager = StateManager(
            deepcopy(parent.cmd_loader), self.local_state, argumentProcessor
        )
        mode_text = (
            i18n.get("editor.mode.edit")
            if model_data
            else i18n.get("editor.mode.new")
        )
        self.title(i18n.get("editor.window.title").format(mode=mode_text))
        self.geometry("1100x750")
        self.transient(parent)
        center_window(self, parent, 1100, 750)
        self.grab_set()
        # self.focus_set()
        self.model_data: Optional[ModelData] = model_data
        self.cmd_loader = self.local_manager.cmd_loader
        self.available_names: List[str] = sorted(
            self.cmd_loader.get_all_names()
        )
        self.params_widgets: List[ParamWidgetRow] = []
        self._image_cache: Dict[str, Image.Image] = {}
        self.e_name: entry.MEntry
        self.e_path: entry.MEntry
        self.scroll: ScrolledFrame
        self.lbl_desc: CopyLabel
        self._init_ui()
        self._refresh_list()
        if model_data:
            if model_data.get("id"):
                self.thumb_view._selected_ids = {model_data["id"]}
                self.thumb_view._update_visuals()
                self.thumb_view._trigger_selection()
        else:
            self._reset_form()

    def _init_ui(self) -> None:
        """Logic: Builds the main layout: Header, Parameter List (Scrolled),
        and Footer buttons."""
        # Toolbar
        toolbar = ttk.Frame(self, padding=5)
        toolbar.pack(fill=X)

        flat.RoundedButton(
            toolbar,
            text=i18n.get("editor.mode.new", "New Model"),
            bootstyle="success",
            width=120,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=self._reset_form,
        ).pack(side=LEFT, padx=5)

        # Paned Window
        self.paned = ttk.Panedwindow(self, orient=HORIZONTAL)
        self.paned.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # Left Pane: Thumb View
        left_frame = ttk.Frame(self.paned, width=320)
        self.paned.add(left_frame, weight=1)

        style = ttk.Style()
        colors = style.colors
        cfg = ThumbViewConfig(
            columns=2,
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
        )
        self.thumb_view.pack(fill=BOTH, expand=True)

        # Right Pane: Editor
        right_frame = ttk.Frame(self.paned, padding=10)
        self.paned.add(right_frame, weight=3)

        self._build_header(right_frame)
        ttk.Separator(right_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

        list_toolbar = ttk.Frame(right_frame)
        list_toolbar.pack(fill=X, pady=(0, 5))
        CopyLabel(
            list_toolbar,
            text=i18n.get("editor.lbl.exec_params"),
            font=(SYSTEM_FONT, 12, "bold"),
            bootstyle="primary",
        ).pack(side=LEFT)
        flat.RoundedButton(
            list_toolbar,
            text=i18n.get("editor.btn.add_param"),
            bootstyle="success",
            height=50,
            corner_radius=CORNER_RADIUS,
            command=lambda: self._create_row("", "", True),
        ).pack(side=RIGHT)

        scroll_container_frame = ttk.Frame(
            right_frame, bootstyle="secondary", padding=1
        )
        scroll_container_frame.pack(fill=tk.BOTH, expand=True)
        self.scroll = ScrolledFrame(scroll_container_frame, autohide=False)
        self.scroll.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._build_footer(right_frame)

    def _build_header(self, parent: ttk.Frame) -> None:
        """Logic: Creates fields for Name, Base Model selection,
        and File Path with browse button."""
        grid_frame = ttk.Frame(parent)
        grid_frame.pack(fill=X)
        grid_frame.columnconfigure(1, weight=1)
        CopyLabel(
            grid_frame,
            text=i18n.get("editor.lbl.profile_name"),
            font=(SYSTEM_FONT, 10, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=5)
        self.e_name = entry.MEntry(
            grid_frame, elevation=1, radius=CORNER_RADIUS
        )
        self.e_name.grid(row=0, column=1, sticky="ew", padx=(2, 0), pady=2)
        CopyLabel(
            grid_frame, text="Base Model:", font=(SYSTEM_FONT, 10, "bold")
        ).grid(row=1, column=0, sticky="w", pady=5)
        self.cb_base_model = ttk.Combobox(
            grid_frame,
            values=KNOWN_BASE_MODELS,
            state="readonly",
            font=(SYSTEM_FONT, 9),
        )
        self.cb_base_model.grid(
            row=1, column=1, sticky="ew", padx=(2, 0), pady=2
        )
        CopyLabel(
            grid_frame,
            text=i18n.get("editor.lbl.model_file"),
            font=(SYSTEM_FONT, 10, "bold"),
        ).grid(row=2, column=0, sticky="w", pady=5)
        path_frame = ttk.Frame(grid_frame)
        path_frame.grid(row=2, column=1, sticky="ew", padx=(2, 0), pady=2)
        self.e_path = entry.MEntry(
            path_frame, elevation=1, radius=CORNER_RADIUS
        )
        self.e_path.pack(side=LEFT, fill=X, expand=True)
        flat.RoundedButton(
            path_frame,
            text="📂",
            bootstyle="secondary",
            height=50,
            width=50,
            corner_radius=CORNER_RADIUS,
            command=self._browse,
        ).pack(side=LEFT, padx=(2, 0))
        CopyLabel(
            grid_frame,
            text=i18n.get("editor.lbl.file_hint"),
            font=(SYSTEM_FONT, 8),
            bootstyle="secondary",
        ).grid(row=3, column=1, sticky="w", padx=(10, 0))

    def _build_footer(self, parent: ttk.Frame) -> None:
        """Logic: Creates help text area and Save/Cancel buttons."""
        pnl_bottom = ttk.Frame(parent, padding=(0, 15, 0, 0))
        pnl_bottom.pack(fill=X, side=BOTTOM)
        info_frame = ttk.Labelframe(
            pnl_bottom,
            text=i18n.get("editor.frame.quick_help"),
            padding=10,
            bootstyle="info",
        )
        info_frame.pack(fill=X, pady=(0, 15))
        self.lbl_desc = CopyLabel(
            info_frame,
            text=i18n.get("editor.lbl.help_desc"),
            bootstyle="secondary",
            wraplength=800,
        )
        self.lbl_desc.pack(fill=X)
        action_frame = ttk.Frame(pnl_bottom)
        action_frame.pack(fill=X)
        flat.RoundedButton(
            action_frame,
            text=i18n.get("lora.btn.close", "Close"),
            bootstyle="secondary",
            command=self.destroy,
            height=50,
            corner_radius=CORNER_RADIUS,
        ).pack(side=LEFT)
        flat.RoundedButton(
            action_frame,
            text=i18n.get("editor.btn.save"),
            bootstyle="primary",
            command=self._save,
            height=50,
            corner_radius=CORNER_RADIUS,
        ).pack(side=RIGHT)

    def _cached_image_loader(
        self,
        path: str,
        size: tuple[int, int],
        callback: Any,
    ) -> None:
        if path in self._image_cache:
            self.after(0, callback, self._image_cache[path], True)
            return

        def _load() -> None:
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
        models = self.parent.models.get_all()
        props_list = []
        for item in models:
            preview = self._find_preview_path(item.get("path"))
            props = ThumbProps(
                id=item["id"],
                image_path=preview,
                description=item.get("name", "Unknown"),
                data=item,
            )
            props_list.append(props)
        self.thumb_view.set_items(props_list)

    def _on_selection_changed(self, selected_items: List[ThumbProps]) -> None:
        if not selected_items:
            return
        self.model_data = selected_items[-1].data
        self._load_data()

    def _reset_form(self) -> None:
        self.model_data = None
        self.e_name.delete(0, tk.END)
        self.e_path.delete(0, tk.END)
        self.cb_base_model.set("")
        self._clear_params()
        self._load_defaults()
        self.thumb_view.clear_selection(notify=False)

    def _load_defaults(self) -> None:
        """Logic: Populates the parameter list with default flags
        defined in configuration."""
        for flag in self.cmd_loader.defaults_flags:
            cmd = self.cmd_loader.get_by_flag(flag)
            if cmd:
                val = str(cmd["default"]) if cmd["default"] is not None else ""
                self._create_row(cmd["name"], val, True)

    def _create_row(self, sel_name: str, val: Any, enabled: bool) -> None:
        """Logic: Adds a dynamic parameter row with Combobox for parameter
        selection and corresponding control widget."""
        row = ttk.Frame(self.scroll, padding=(5, 5, 15, 5))
        row.pack(fill=X, pady=2)
        combo = ttk.Combobox(
            row,
            values=self.available_names,
            width=30,
            state="readonly",
            font=(SYSTEM_FONT, 9),
        )
        combo.set(
            sel_name
            if sel_name in self.available_names
            else i18n.get("editor.combo.select")
        )
        combo.pack(side=LEFT, padx=(0, 10))
        ctrl_container = ttk.Frame(row)
        ctrl_container.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        btn_del = flat.RoundedButton(
            row,
            text="✕",
            bootstyle="danger",
            width=40,
            height=40,
            corner_radius=CORNER_RADIUS,
            command=lambda: self._del_row(row),
        )
        btn_del.pack(side=LEFT)
        row_data: ParamWidgetRow = {
            "frame": row,
            "combo": combo,
            "ctrl_container": ctrl_container,
            "ctrl": None,
            "delete_btn": btn_del,
        }
        self.params_widgets.append(row_data)

        def on_change(_event: Optional[tk.Event] = None) -> None:
            choice = combo.get()
            cmd = self.cmd_loader.get_by_name(choice)
            if not cmd:
                return
            self.lbl_desc.configure(
                text=f"ℹ [{cmd['flag']}] {cmd['desc']}", bootstyle="info"
            )
            self._update_ctrl_in_row(row_data, cast(Dict[str, Any], cmd))

        combo.bind("<<ComboboxSelected>>", on_change)
        if sel_name:
            cmd_init = self.cmd_loader.get_by_name(sel_name)
            if cmd_init:
                self._update_ctrl_in_row(
                    row_data,
                    cast(Dict[str, Any], cmd_init),
                    initial_value=val,
                    initial_enabled=enabled,
                )

    def _update_ctrl_in_row(
        self,
        row_data: ParamWidgetRow,
        cmd: Dict[str, Any],
        initial_value: Any = None,
        initial_enabled: bool = True,
    ) -> None:
        """Logic: Replaces the control widget in a row based on the selected
        parameter type (e.g., switch from int input to toggle)."""
        container = row_data["ctrl_container"]
        for child in container.winfo_children():
            child.destroy()
        ctrl = self.local_manager.new_argument_control(container, cmd["flag"])
        if not ctrl:
            return
        ctrl.pack(fill=X, expand=True)
        if hasattr(ctrl, "lbl_name"):
            ctrl.lbl_name.grid_remove()  # type: ignore
        if initial_value is not None:
            ctrl.set_value(initial_value)
        elif cmd.get("default") is not None:
            ctrl.set_value(cmd["default"])
        ctrl.var_enabled.set(initial_enabled)
        ctrl.toggle_state()
        row_data["ctrl"] = ctrl

    def _del_row(self, row_frame: ttk.Frame) -> None:
        """Logic: Removes a parameter row from the UI and internal list."""
        row_frame.destroy()
        self.params_widgets = [
            p for p in self.params_widgets if p["frame"].winfo_exists()
        ]

    def _clear_params(self) -> None:
        for row in self.params_widgets:
            row["frame"].destroy()
        self.params_widgets.clear()

    def _browse(self) -> None:
        """Logic: Opens file dialog to select model file path."""
        file_path = filedialog.askopenfilename(
            filetypes=[
                (
                    i18n.get("editor.filetype.models"),
                    "*.gguf *.bin *.safetensors",
                ),
                (i18n.get("editor.filetype.all"), "*.*"),
            ]
        )
        if file_path:
            self.e_path.delete(0, tk.END)
            self.e_path.insert(0, file_path)

    def _load_data(self) -> None:
        """Logic: Populates fields and parameter rows from existing
        model data (Edit mode)."""
        if not self.model_data:
            return
        self._clear_params()
        self.e_name.delete(0, tk.END)
        self.e_name.insert(0, self.model_data["name"])
        self.e_path.delete(0, tk.END)
        self.e_path.insert(0, self.model_data["path"])
        if base := self.model_data.get("base_model"):
            if base in KNOWN_BASE_MODELS:
                self.cb_base_model.set(base)
            else:
                self.cb_base_model.set(base)
        for param in self.model_data["params"]:
            flag = param.get("flag", "")
            cmd = self.cmd_loader.get_by_flag(flag)
            name = cmd["name"] if cmd else flag
            if name not in self.available_names:
                self.available_names.append(name)
                self.available_names.sort()
            self._create_row(
                name, param["value"], bool(param.get("enabled", True))
            )

    def _save(self) -> None:
        """Logic: Validates inputs, gathers all parameters, saves/updates
        the model via parent manager, and closes window."""
        name = self.e_name.get().strip()
        path = self.e_path.get().strip()
        base_model = self.cb_base_model.get().strip()
        if not name or not path:
            messagebox.showerror(
                i18n.get("editor.msg.attention"),
                i18n.get("editor.msg.required_fields"),
            )
            return
        final_params: List[Dict[str, Any]] = []
        for widget_row in self.params_widgets:
            if widget_row["frame"].winfo_exists():
                ctrl = widget_row["ctrl"]
                if not ctrl:
                    continue
                flag = ctrl.flag
                val = ctrl.var_value.get()
                is_enabled = ctrl.var_enabled.get()
                if flag:
                    final_params.append(
                        {"flag": flag, "value": val, "enabled": is_enabled}
                    )
        model_id = self.model_data["id"] if self.model_data else None
        self.parent.models.add_or_update_model(
            model_id, name, path, final_params, base_model=base_model
        )
        self.parent.refresh_models_list()
        self._refresh_list()
        messagebox.showinfo("Saved", f"Model '{name}' saved successfully.")
