"""
Base class for Network Sections (LoRA/Embedding) with Selection Logic.
"""

from __future__ import annotations

from tkinter import filedialog
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple, cast

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, HORIZONTAL, LEFT, RIGHT, X

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.domain.utils.compatibility import CompatibilityService
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.plugins.shared_ui.network_picker import NetworkPickerDialog
from sd_cpp_gui.plugins.shared_ui.network_widgets import GhostNetworkWidget
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class NetworkSection(ttk.Frame):
    """
    Base class for a list of network items (LoRAs/Embeddings).
    Implements a 'Select & Add' workflow to keep the UI clean.
    """

    def __init__(
        self,
        parent: ttk.Frame,
        manager: Any,
        title: str,
        editor_callback: Callable[[], None],
        widget_class: Any,
        on_param_change: Optional[Callable[[str, str, Any, bool], None]],
    ) -> None:
        """Logic: Initializes base network section."""
        super().__init__(parent)
        self.manager = manager
        self.title = title
        self.editor_callback = editor_callback
        self.on_param_change = on_param_change
        self.WidgetClass = widget_class
        self.var_add_triggers = ttk.BooleanVar(value=False)
        self.library_data: Dict[str, Dict[str, Any]] = {}
        self.aliases: Dict[str, str] = {}
        self.active_items: Dict[str, Tuple[ttk.Frame, Any]] = {}
        self.current_base_model: Optional[str] = None
        self._init_ui()

    def _init_ui(self) -> None:
        """Logic: Builds UI."""
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=X, pady=(0, 5))
        CopyLabel(
            header_frame,
            text=self.title,
            font=(SYSTEM_FONT, 12, "bold"),
            bootstyle="primary",
        ).pack(side=LEFT)
        if self.editor_callback is not None:
            flat.RoundedButton(
                header_frame,
                text="⚙️",
                width=36,
                height=40,
                corner_radius=CORNER_RADIUS,
                bootstyle="primary",
                command=self.editor_callback,
            ).pack(side=RIGHT, anchor="center")
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(fill=X, pady=(0, 5))
        f_folder = ttk.Frame(self.toolbar)
        f_folder.pack(fill=X, pady=2)
        f_folder.columnconfigure(1, weight=1)
        CopyLabel(f_folder, text="📁", font=(SYSTEM_FONT, 10)).grid(
            row=0, column=0, padx=(0, 5)
        )
        self.cb_folders = ttk.Combobox(
            f_folder, state="readonly", font=(SYSTEM_FONT, 9)
        )
        self.cb_folders.grid(row=0, column=1, sticky="ew")
        self.cb_folders.bind("<<ComboboxSelected>>", self._on_folder_selected)
        flat.RoundedButton(
            f_folder,
            text="Scan",
            width=64,
            height=40,
            corner_radius=CORNER_RADIUS,
            bootstyle="secondary",
            command=self._import_folder,
        ).grid(row=0, column=2, padx=(5, 0))
        f_select = ttk.Frame(self.toolbar)
        f_select.pack(fill=X, pady=(5, 0))
        f_select.columnconfigure(0, weight=1)
        self.cb_available = ttk.Combobox(
            f_select, state="readonly", font=(SYSTEM_FONT, 9)
        )
        self.cb_available.pack(side=LEFT, fill=X, expand=True)
        self.cb_available.set(
            i18n.get("common.select_item", "Select model to add...")
        )
        flat.RoundedButton(
            f_select,
            text="🔎",
            width=40,
            height=40,
            corner_radius=CORNER_RADIUS,
            bootstyle="info",
            command=self._open_picker,
        ).pack(side=LEFT, padx=(5, 0))
        flat.RoundedButton(
            f_select,
            text="➕ Add",
            width=64,
            height=40,
            corner_radius=CORNER_RADIUS,
            bootstyle="success",
            command=self._add_current_selection,
        ).pack(side=LEFT, padx=(5, 0))
        ttk.Separator(self, orient=HORIZONTAL).pack(fill=X, pady=5)
        chk = ttk.Checkbutton(
            self.toolbar,
            variable=self.var_add_triggers,
            text=i18n.get("lora.add_triggers"),
            bootstyle="round-toggle",
        )
        chk.pack(side=RIGHT, padx=5, pady=5)
        self.scroll_frame = ttk.Frame(self)
        self.scroll_frame.pack(fill=BOTH, expand=True)
        self.refresh_list()

    def _open_picker(self) -> None:
        """
        Opens the rich visual picker dialog.
        Filters items based on CompatibilityService to remove
        incompatible models.

        Logic: Opens picker.
        """
        all_items = self.manager.get_all()
        valid_items = []
        for item in all_items:
            res_base = item.get("base_model")
            status = CompatibilityService.check(
                self.current_base_model, res_base
            )
            if status == "incompatible":
                continue
            item_display = item.copy()
            item_display["_compatibility_status"] = status
            valid_items.append(item_display)
        valid_items.sort(
            key=lambda x: (x.get("alias") or x.get("name", "")).lower()
        )
        picker = NetworkPickerDialog(
            parent=self,
            title=self.title,
            items=valid_items,
            on_select=self._add_item_to_view,
        )
        picker.grab_set()

    def _import_folder(self) -> None:
        """Logic: Imports folder."""
        folder = filedialog.askdirectory(parent=self)
        if folder:
            count = self.manager.scan_and_import_folder(folder)
            if count > 0:
                self.refresh_list()
                self.cb_folders.set(folder)
                self._on_folder_selected(None)

    def refresh_list(self) -> None:
        """Refreshes the folder list and current library.

        Logic: Refreshes list."""
        folders = self.manager.get_known_folders()
        self.cb_folders["values"] = folders
        if folders:
            current = self.cb_folders.get()
            if not current or current not in folders:
                self.cb_folders.current(0)
            self._on_folder_selected(None)
        else:
            self.cb_folders.set("")
            self.library_data.clear()
            self.cb_available["values"] = []

    def set_base_model_filter(self, base_model: Optional[str]) -> None:
        """Updates the available list based on the selected Checkpoint.

        Logic: Updates base model filter."""
        self.current_base_model = base_model
        self._update_available_combo()

    def _on_folder_selected(self, _event: Any) -> None:
        """Loads items from folder.

        Logic: Loads items on folder selection."""
        folder = self.cb_folders.get()
        if not folder:
            return
        items = self.manager.get_by_folder(folder)
        self.library_data = {
            item.get("name", "Unknown"): item for item in items
        }
        self._update_available_combo()

    def _update_available_combo(self) -> None:
        """Filters and sorts the combobox values based on compatibility.

        Logic: Updates combobox values."""
        if not self.library_data:
            self.cb_available["values"] = []
            self.cb_available.set("")
            return
        compatible = []
        possible = []
        unknown = []
        for name, item in self.library_data.items():
            res_base = item.get("base_model")
            status = CompatibilityService.check(
                self.current_base_model, res_base
            )
            alias = item.get("alias") or item.get("name")
            if status == "compatible":
                compatible.append(alias)
            elif status == "possible":
                possible.append(f"⚠️ {alias} ({res_base})")
            elif status == "unknown":
                unknown.append(f"❓ {alias}")
        final_values = sorted(compatible) + sorted(possible) + sorted(unknown)
        self.cb_available["values"] = final_values
        self.aliases = {}
        for name, item in self.library_data.items():
            raw_alias = item.get("alias") or item.get("name")
            res_base = item.get("base_model", "Unknown")
            if not raw_alias:
                continue
            self.aliases[raw_alias] = name
            self.aliases[f"⚠️ {raw_alias} ({res_base})"] = name
            self.aliases[f"❓ {raw_alias}"] = name
        if final_values:
            self.cb_available.set(
                i18n.get("common.select_item", "Select item...")
            )
        else:
            self.cb_available.set("No compatible items found")

    def _add_current_selection(self) -> None:
        """Manually adds the selected item from the combobox.

        Logic: Adds selected item."""
        selection = self.cb_available.get()
        if not selection:
            return
        if selection in self.aliases:
            name = self.aliases[selection]
            if name in self.library_data:
                self._add_item_to_view(self.library_data[name])

    def _add_item_to_view(self, item_data: Dict[str, Any]) -> None:
        """Creates the widget for the item if it doesn't exist.

        Logic: Adds item widget."""
        name = item_data.get("name", "Unknown")
        if name in self.active_items:
            return
        container = ttk.Frame(self.scroll_frame)
        container.pack(fill=X, pady=2)
        widget = cast(Any, self.WidgetClass)(
            container,
            item_data,
            on_change=self.on_param_change,
            on_remove=lambda: self._remove_item(name),
        )
        widget.pack(side=LEFT, fill=X, expand=True)
        widget.var_enabled.set(True)
        widget.toggle_state()
        self.active_items[name] = (container, widget)

    def _remove_item(self, name: str) -> None:
        """Removes the item from the view and notifies state.

        Logic: Removes item widget."""
        if name in self.active_items:
            container, _widget = self.active_items[name]
            arg_type = (
                "lora"
                if self.WidgetClass.__name__ == "LoraWidget"
                else "embedding"
            )
            if self.on_param_change:
                self.on_param_change(arg_type, name)
            container.destroy()
            del self.active_items[name]

    def _add_ghost_item_to_view(self, name: str, data: Dict[str, Any]) -> None:
        """Creates a GhostWidget for items missing from the library.

        Logic: Adds ghost widget."""
        if name in self.active_items:
            return
        container = ttk.Frame(self.scroll_frame)
        container.pack(fill=X, pady=2)
        widget = GhostNetworkWidget(
            container,
            name=name,
            on_remove=lambda: self._remove_item(name),
            data=data,
        )
        widget.pack(side=LEFT, fill=X, expand=True)
        self.active_items[name] = (container, widget)

    def sync_with_state(self, state: Dict[str, Any]) -> None:
        """
        Updates widgets from state (legacy dict structure from get_full_state).
        Values are now (strength, dir, triggers) or (target, strength,
        dir, triggers).

        Logic: Syncs UI with state.
        """
        network_type = (
            "loras"
            if self.WidgetClass.__name__ == "LoraWidget"
            else "embeddings"
        )
        active_networks = state.get(network_type, {})
        for name in list(self.active_items.keys()):
            if name not in active_networks:
                _, widget = self.active_items[name]
                if isinstance(widget, GhostNetworkWidget):
                    self._remove_item(name)
                else:
                    widget.update_remote(enabled=False, value=None)
        for name, value in active_networks.items():
            if name not in self.active_items:
                if name in self.library_data:
                    self._add_item_to_view(self.library_data[name])
                else:
                    ghost_data = {}
                    if isinstance(value, tuple) and len(value) > 1:
                        if self.WidgetClass.__name__ == "LoraWidget":
                            ghost_data = {"strength": value[0]}
                            if len(value) > 3:
                                ghost_data["content_hash"] = value[3]
                                ghost_data["remote_version_id"] = value[4]
                        else:
                            ghost_data = {
                                "target": value[0],
                                "strength": value[1],
                            }
                            if len(value) > 5:
                                ghost_data["content_hash"] = value[4]
                                ghost_data["remote_version_id"] = value[5]
                    self._add_ghost_item_to_view(name, ghost_data)
            if name in self.active_items:
                _, widget = self.active_items[name]
                widget.update_remote(enabled=True, value=value)

    def reset(self) -> None:
        """Resets all widgets (disables them, doesn't remove them).

        Logic: Resets all widgets."""
        for name, (_, widget) in list(self.active_items.items()):
            arg_type = (
                "lora"
                if self.WidgetClass.__name__ == "LoraWidget"
                else "embedding"
            )
            if self.on_param_change:
                self.on_param_change(arg_type, name)
            widget.reset()
