from tkinter import filedialog
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, HORIZONTAL, X

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.core.i18n import get_i18n
from sd_cpp_gui.ui.argument_manager import ArgumentManager
from sd_cpp_gui.ui.components import flat

if TYPE_CHECKING:
    from sd_cpp_gui.ui.panels.net_tab.widgets import EmbeddingWidget, LoraWidget

i18n = get_i18n()


class NetworkSection(ttk.Frame):
    """Base class for a list of network items."""

    def __init__(
        self,
        parent,
        manager,
        title,
        editor_callback,
        widget_class,
        on_param_change,
        args_manager: Optional[ArgumentManager],
    ):
        super().__init__(parent)
        self.manager = manager
        self.title = title
        self.editor_callback = editor_callback
        self.on_param_change = on_param_change
        self.WidgetClass = widget_class
        self.widgets: List["LoraWidget" | "EmbeddingWidget"] = []
        self.args_manager = args_manager
        self._init_ui()

    def _init_ui(self):
        ttk.Label(
            self, text=self.title, font=(SYSTEM_FONT, 12, "bold"), bootstyle="primary"
        ).pack(fill=X, pady=(0, 10))

        self.toolbar = ttk.Frame(self)
        self.toolbar.columnconfigure(1, weight=1)
        self.toolbar.pack(fill=X, pady=(0, 5))

        ttk.Label(
            self.toolbar,
            text=f"{i18n.get('lora.lbl.library_folder')}:",
            font=(SYSTEM_FONT, 9),
        ).grid(column=0, row=0, padx=(0, 5))

        self.cb_folders = ttk.Combobox(self.toolbar, state="readonly")
        self.cb_folders.grid(column=1, row=0, padx=(0, 5), sticky="ew")
        self.cb_folders.bind("<<ComboboxSelected>>", self._on_folder_selected)

        # Scan New Folder Button
        flat.RoundedButton(
            self.toolbar,
            text="📂",
            width=40,
            height=40,
            corner_radius=14,
            bootstyle="success",
            command=self._import_folder,
        ).grid(column=2, row=0, padx=2)

        if self.editor_callback:
            flat.RoundedButton(
                self.toolbar,
                text="⚙️",
                width=40,
                height=40,
                corner_radius=14,
                bootstyle="secondary",
                command=self.editor_callback,
            ).grid(column=3, row=0, padx=2)

        flat.RoundedButton(
            self.toolbar,
            text="🔄",
            width=40,
            height=40,
            corner_radius=14,
            bootstyle="info",
            command=self.refresh_list,
        ).grid(column=4, row=0, padx=(0, 5))

        ttk.Separator(self, orient=HORIZONTAL).pack(fill=X, pady=5)
        self.scroll_frame = ttk.Frame(self)
        self.scroll_frame.pack(fill=BOTH, expand=True)
        self.refresh_list()

    def _import_folder(self):
        folder = filedialog.askdirectory(parent=self)
        if folder:
            count = self.manager.scan_and_import_folder(folder)
            if count > 0:
                self.refresh_list()
                self.cb_folders.set(folder)
                self._on_folder_selected(None)

    def refresh_list(self):
        folders = self.manager.get_known_folders()
        self.cb_folders["values"] = folders
        if folders:
            current = self.cb_folders.get()
            if not current or current not in folders:
                self.cb_folders.current(0)
            self._on_folder_selected(None)
        else:
            self.cb_folders.set("")
            self._clear_list()

    def _on_folder_selected(self, _event):
        # This method needs to be implemented or overridden, but based on original code
        # it relies on WidgetClass and manager which are passed in __init__.
        # However, the original implementation was in the same file as widgets.
        # Here we need to ensure WidgetClass is compatible.
        folder = self.cb_folders.get()
        if not folder:
            return
        self._clear_list()
        items = self.manager.get_by_folder(folder)
        if not items:
            ttk.Label(
                self.scroll_frame,
                text=i18n.get("lora.msg.empty_folder"),
                bootstyle="secondary",
            ).pack(pady=10)
            return

        # We need to determine arg_type. In original code it checked class type.
        # We can infer it or pass it. For now, we use the class name string check or attribute.
        arg_type = "lora" if self.WidgetClass.__name__ == "LoraWidget" else "embedding"

        for item in items:
            w = self.WidgetClass(
                self.scroll_frame, item, on_change=self.on_param_change
            )
            w.pack(fill=X, pady=4, padx=5)

            self.args_manager.register_param_control(
                arg_type, w.data.get("name", w.name), w
            )
            self.widgets.append(w)

    def _clear_list(self):
        arg_type = "lora" if self.WidgetClass.__name__ == "LoraWidget" else "embedding"
        if self.on_param_change:
            for w in self.widgets:
                self.on_param_change(False, arg_type, w.data.get("name", w.name), None)

        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.widgets = []

    def get_active_data(self) -> List[Dict[str, Any]]:
        return [data for w in self.widgets if (data := w.get_data_if_active())]

    def reset(self):
        """Resets all widgets in this section."""
        for widget in self.widgets:
            widget.reset()
