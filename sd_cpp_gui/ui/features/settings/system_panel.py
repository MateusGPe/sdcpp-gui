"""
System configuration panel.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Callable, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.constants import LEFT, X

from sd_cpp_gui.constants import (
    CHANNEL_APP_EVENTS,
    CORNER_RADIUS,
    MSG_DATA_IMPORTED,
    SYSTEM_FONT,
)
from sd_cpp_gui.infrastructure.event_bus import EventBus
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.entry import MEntry
from sd_cpp_gui.ui.components.utils import CopyLabel
from sd_cpp_gui.ui.features.maintenance.sanitizer_window import SanitizerWindow

if TYPE_CHECKING:
    from sd_cpp_gui.data.db.data_manager import (
        EmbeddingManager,
        HistoryManager,
        LoraManager,
        ModelManager,
        SettingsManager,
    )
    from sd_cpp_gui.domain.generation.interfaces import IGenerator
    from sd_cpp_gui.infrastructure.i18n import I18nManager
    from sd_cpp_gui.ui.execution_manager import ExecutionManager

i18n: I18nManager = get_i18n()


class SystemPanel(ttk.Frame):
    """System configuration panel."""

    def __init__(
        self,
        parent: tk.Widget,
        settings_manager: SettingsManager,
        runner: IGenerator,
        model_manager: ModelManager,
        history_manager: HistoryManager,
        lora_manager: LoraManager,
        embedding_manager: EmbeddingManager,
        execution_manager: Optional[ExecutionManager],
    ) -> None:
        """Logic: Initializes settings, managers, UI variables,
        and builds the UI layout."""
        super().__init__(parent)
        self.settings = settings_manager
        self.runner = runner
        self.managers = {
            "Models": model_manager,
            "History": history_manager,
            "LoRAs": lora_manager,
            "Embeddings": embedding_manager,
        }
        self.execution_manager = execution_manager
        self.vars = {
            "exe_path": tk.StringVar(value=self.settings.get_app()),
            "output_path": tk.StringVar(value=self.settings.get_output_dir()),
            "server_exe": tk.StringVar(
                value=self.settings.get("server_executable_path", "")
            ),
            "exec_mode": tk.StringVar(
                value=self.settings.get("execution_mode", "auto")
            ),
            "host": tk.StringVar(
                value=self.settings.get("server_host", "127.0.0.1")
            ),
            "port": tk.StringVar(
                value=self.settings.get("server_port", "1234")
            ),
            "process_mode": tk.StringVar(
                value=self.settings.get("server_process_mode", "start_local")
            ),
            "locale": tk.StringVar(value=i18n.current_locale),
            "ui_scale": tk.IntVar(
                value=int(self.settings.get("ui_scale", "2"))
            ),
            "ui_res1": tk.StringVar(
                value=self.settings.get("ui_first_quality", "Nearest")
            ),
            "ui_res2": tk.StringVar(
                value=self.settings.get("ui_quality", "Bicubic")
            ),
        }
        self._init_ui()
        self._setup_bindings()

    def _setup_bindings(self) -> None:
        """Configures auto-save for simple text fields.

        Logic: Configures auto-save traces for text fields like host,
        port, execution mode, etc."""

        def _bind(var_key: str, setting_key: str):
            self.vars[var_key].trace_add(
                "write",
                lambda *_: self.settings.set(
                    setting_key, self.vars[var_key].get()
                ),
            )

        _bind("host", "server_host")
        _bind("port", "server_port")
        _bind("exec_mode", "execution_mode")
        _bind("process_mode", "server_process_mode")

    def _init_ui(self) -> None:
        """Logic: Constructs the UI sections: CLI config, Server config,
        Output dir, Interface settings, and Data management buttons."""
        self._add_section_header(
            "system.lbl.executable_config", "CLI Configuration"
        )
        self._add_file_picker_row(
            self.vars["exe_path"],
            "system.btn.sd_cpp",
            "Browse CLI",
            self._browse_app,
        )
        self._add_note("system.lbl.note_binary")
        self._add_separator()
        self._add_section_header(
            "system.lbl.server_config", "Backend / Server Configuration"
        )
        self._add_combo_row(
            "system.lbl.execution_mode",
            "Execution Mode",
            self.vars["exec_mode"],
            ["auto", "cli_only", "server_only"],
        )
        self._add_combo_row(
            "system.lbl.server_process_mode",
            "Server Process",
            self.vars["process_mode"],
            ["start_local", "external"],
        )
        self._add_file_picker_row(
            self.vars["server_exe"],
            "system.btn.sd_server",
            "Browse Server",
            self._browse_server_app,
        )
        self._add_note(
            "system.lbl.note_server_exe", "Path to 'sd-server' executable."
        )
        f_net = ttk.Frame(self)
        f_net.pack(fill=X, pady=15)
        f_net.columnconfigure((1, 3), weight=1)
        CopyLabel(f_net, text=i18n.get("system.lbl.host", "Host:")).grid(
            row=0, column=0, padx=(0, 5), sticky="w"
        )
        MEntry(f_net, textvariable=self.vars["host"], width=15).grid(
            row=0, column=1, padx=(0, 5), sticky="ew"
        )
        CopyLabel(f_net, text=i18n.get("system.lbl.port", "Port:")).grid(
            row=0, column=2, padx=(0, 5), sticky="w"
        )
        MEntry(f_net, textvariable=self.vars["port"], width=8).grid(
            row=0, column=3, sticky="ew"
        )
        self._add_note(
            "system.lbl.note_network",
            "Server mode allows access over the network.",
        )
        self._add_separator()
        self._add_section_header(
            "system.lbl.output_dir_config", "Output Directory"
        )
        self._add_file_picker_row(
            self.vars["output_path"],
            "system.btn.output_dir",
            "Browse",
            self._browse_output_dir,
        )
        self._add_separator()
        self._add_section_header(
            "system.lbl.interface_config", "Interface Configuration"
        )
        f_lang = ttk.Frame(self)
        f_lang.pack(fill=X, pady=(0, 10))
        CopyLabel(
            f_lang, text=i18n.get("system.lbl.language_config", "Language:")
        ).pack(side=LEFT, padx=(0, 10))
        cb_lang = ttk.Combobox(
            f_lang,
            textvariable=self.vars["locale"],
            values=i18n.get_locales(),
            state="readonly",
        )
        cb_lang.pack(side=LEFT, fill=X, expand=True)
        cb_lang.bind("<<ComboboxSelected>>", self._on_lang_change)
        f_ui = ttk.Frame(self)
        f_ui.pack(fill=X, pady=5)
        f_ui.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self._add_grid_combo(
            f_ui,
            0,
            i18n.get("system.lbl.ui_scale_label", "Scale:"),
            self.vars["ui_scale"],
            list(range(1, 16)),
            8,
        )
        self._add_grid_combo(
            f_ui,
            2,
            i18n.get("system.lbl.ui_res1", "1-2 Res.:"),
            self.vars["ui_res1"],
            ["Nearest", "Bilinear", "Bicubic", "Lanczos"],
            12,
        )
        self._add_grid_combo(
            f_ui,
            4,
            i18n.get("system.lbl.ui_res2", "2+ Res.:"),
            self.vars["ui_res2"],
            ["Nearest", "Bilinear", "Bicubic", "Lanczos"],
            12,
        )
        self._add_note("system.lbl.note_restart", "Changes require restart.")
        self._add_separator()
        self._add_section_header(
            "system.lbl.data_management", "Data Management"
        )
        f_data = ttk.Frame(self)
        f_data.pack(fill=X)
        f_data.columnconfigure((0, 1, 2), weight=1)
        flat.RoundedButton(
            f_data,
            text=i18n.get("system.btn.import"),
            width=110,
            height=50,
            corner_radius=CORNER_RADIUS,
            bootstyle="secondary",
            command=self._import_data,
        ).grid(row=0, column=0, padx=0, sticky="ew")
        flat.RoundedButton(
            f_data,
            text=i18n.get("system.btn.export"),
            width=110,
            height=50,
            corner_radius=CORNER_RADIUS,
            bootstyle="secondary",
            command=self._export_data,
        ).grid(row=0, column=1, padx=5, sticky="ew")
        flat.RoundedButton(
            f_data,
            text=i18n.get("system.btn.sanitize", "🛠️ Sanitize Library"),
            width=140,
            height=50,
            corner_radius=CORNER_RADIUS,
            bootstyle="warning",
            command=lambda: SanitizerWindow(self.winfo_toplevel()),
        ).grid(row=0, column=2, sticky="ew")
        for widget in self.winfo_children():
            if isinstance(widget, CopyLabel):
                widget.bind(
                    "<Configure>",
                    lambda e, w=widget: w.config(wraplength=w.winfo_width()),
                )

    def _add_section_header(self, key: str, default: str):
        """Logic: Adds a bold label header for a settings section."""
        CopyLabel(
            self, text=i18n.get(key, default), font=(SYSTEM_FONT, 12, "bold")
        ).pack(fill=X, pady=(0, 15))

    def _add_separator(self):
        """Logic: Adds a visual separator line between sections."""
        ttk.Separator(self, style="secondary.Horizontal.TSeparator").pack(
            fill=X, pady=20
        )

    def _add_note(self, key: str, default: str = ""):
        """Logic: Adds a small explanatory note label below a setting."""
        CopyLabel(
            self,
            text=i18n.get(key, default),
            bootstyle="secondary",
            font=(SYSTEM_FONT, 9),
        ).pack(anchor="w", expand=True, fill=X, pady=(5, 0))

    def _add_file_picker_row(
        self, var: tk.StringVar, btn_key: str, btn_def: str, cmd: Callable
    ):
        """Logic: Creates a row with a readonly entry and a browse button
        for file/folder selection."""
        f = ttk.Frame(self)
        f.pack(fill=X)
        f.columnconfigure(0, weight=1)
        MEntry(f, textvariable=var, state="readonly").grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        flat.RoundedButton(
            f,
            text=i18n.get(btn_key, btn_def),
            width=120,
            height=50,
            corner_radius=CORNER_RADIUS,
            bootstyle="secondary",
            command=cmd,
        ).grid(row=0, column=1)

    def _add_combo_row(
        self, label_key: str, label_def: str, var: tk.StringVar, values: list
    ):
        """Logic: Creates a labeled combobox row for selecting options like
        execution mode."""
        f = ttk.Frame(self)
        f.pack(fill=X, pady=(0, 10))
        CopyLabel(f, text=i18n.get(label_key, label_def)).pack(
            side=LEFT, padx=(0, 10)
        )
        cb = ttk.Combobox(f, textvariable=var, values=values, state="readonly")
        cb.pack(side="right", fill=X, expand=True)

    def _add_grid_combo(self, parent, col, text, var, values, width):
        """Logic: Adds a label and combobox to a specific grid column
        (used for UI scaling options)."""
        CopyLabel(parent, text=text).grid(
            row=0, column=col, sticky="w", padx=(0, 5)
        )
        cb = ttk.Combobox(
            parent,
            textvariable=var,
            values=values,
            state="readonly",
            width=width,
        )
        cb.grid(row=0, column=col + 1, sticky="ew", padx=(0, 15))
        cb.bind("<<ComboboxSelected>>", self._on_ui_change)

    def _browse_output_dir(self) -> None:
        """Logic: Opens directory dialog to set output path
        and updates settings."""
        if f := filedialog.askdirectory():
            self.settings.set_output_dir(f)
            self.vars["output_path"].set(f)
            messagebox.showinfo(
                i18n.get("system.msg.success_title", "Success"),
                i18n.get("system.msg.output_dir_set", "Output directory set!"),
            )

    def _browse_app(self) -> None:
        """Logic: Opens file dialog to select CLI executable and
        updates settings/runners."""
        if f := filedialog.askopenfilename():
            if os.access(f, os.X_OK):
                self.settings.set_app(f)
                self.runner.executable_path = f
                if self.execution_manager:
                    self.execution_manager.cli_runner.executable_path = f
                self.vars["exe_path"].set(f)
                messagebox.showinfo(
                    i18n.get("system.msg.success_title", "Success"),
                    i18n.get("system.msg.executable_set", "Executable set!"),
                )

    def _browse_server_app(self) -> None:
        """Logic: Opens file dialog to select Server executable
        and updates settings."""
        if f := filedialog.askopenfilename():
            self.settings.set("server_executable_path", f)
            if self.execution_manager:
                self.execution_manager.server_runner.executable_path = f
            self.vars["server_exe"].set(f)

    def _on_lang_change(self, _e=None) -> None:
        """Logic: Updates language setting and prompts restart if changed."""
        if (
            new_lang := self.vars["locale"].get()
        ) and new_lang != i18n.current_locale:
            self.settings.set("language", new_lang)
            messagebox.showinfo(
                i18n.get("system.msg.restart_title", "Restart Required"),
                i18n.get("system.msg.language_set", "Language changed."),
            )

    def _on_ui_change(self, _e=None) -> None:
        """Logic: Updates UI scale/quality settings and prompts restart."""
        self.settings.set("ui_scale", self.vars["ui_scale"].get())
        self.settings.set("ui_first_quality", self.vars["ui_res1"].get())
        self.settings.set("ui_quality", self.vars["ui_res2"].get())
        messagebox.showinfo(
            i18n.get("system.msg.restart_title", "Restart Required"),
            i18n.get("system.msg.restart_required", "Please restart..."),
        )

    def _data_dialog(self, title_key: str) -> Optional[Tuple[str, str]]:
        """Logic: Shows a modal dialog to select Data Type (Models, etc.)
        and Format (JSON, etc.) for import/export."""
        title = i18n.get(title_key, "Data")
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("300x220")
        dialog.transient(self)  # type: ignore
        dialog.grab_set()
        result: list[Optional[Tuple[str, str]]] = [None]

        # Localized mapping for data types
        type_map = {
            i18n.get("data_manager.models_window_title", "Models"): "Models",
            i18n.get("history.window.title", "History"): "History",
            i18n.get("cat.lora", "LoRAs"): "LoRAs",
            i18n.get("cat.embedding", "Embeddings"): "Embeddings",
        }
        type_var = tk.StringVar(value=list(type_map.keys())[0])
        fmt_var = tk.StringVar(value="JSON")
        CopyLabel(
            dialog, text=i18n.get("system.dialog.data_type", "Data Type:")
        ).pack(pady=5)
        ttk.Combobox(
            dialog,
            textvariable=type_var,
            values=list(type_map.keys()),
            state="readonly",
        ).pack(fill=X, padx=10)
        CopyLabel(
            dialog, text=i18n.get("system.dialog.format", "Format:")
        ).pack(pady=5)
        ttk.Combobox(
            dialog,
            textvariable=fmt_var,
            values=["JSON", "YAML", "TOML"],
            state="readonly",
        ).pack(fill=X, padx=10)

        def _confirm():
            result[0] = (type_map.get(type_var.get(), "Models"), fmt_var.get())
            dialog.destroy()

        ttk.Button(
            dialog, text=i18n.get("system.dialog.ok", "OK"), command=_confirm
        ).pack(pady=20)
        self.wait_window(dialog)
        return result[0]

    def _import_data(self) -> None:
        """Logic: Handles data import process: shows dialog, selects file,
        calls manager import method, and publishes event."""
        if not (sel := self._data_dialog("system.msg.import_title")):
            return
        dtype, fmt = sel
        ext = f".{fmt.lower()}"
        fname = filedialog.askopenfilename(
            filetypes=[(f"{fmt} files", f"*{ext}")]
        )
        if not fname:
            return
        try:
            mgr = self.managers[dtype]
            getattr(mgr, f"import_from_{fmt.lower()}")(fname)
            messagebox.showinfo(
                i18n.get("system.msg.success", "Success"),
                i18n.get("system.msg.imported", "Imported successfully!"),
            )
            EventBus.publish(
                CHANNEL_APP_EVENTS,
                {"type": MSG_DATA_IMPORTED, "payload": {"data_type": dtype}},
            )
        except Exception as e:
            msg = i18n.get(
                "system.msg.import_fail", "Import failed: {error}"
            ).format(error=e)
            messagebox.showerror(i18n.get("status.error", "Error"), msg)

    def _export_data(self) -> None:
        """Logic: Handles data export process: shows dialog, selects save file,
        and calls manager export method."""
        if not (sel := self._data_dialog("system.msg.export_title")):
            return
        dtype, fmt = sel
        ext = f".{fmt.lower()}"
        fname = filedialog.asksaveasfilename(
            defaultextension=ext, filetypes=[(f"{fmt} files", f"*{ext}")]
        )
        if not fname:
            return
        try:
            getattr(self.managers[dtype], f"export_to_{fmt.lower()}")(fname)
            msg = i18n.get("system.msg.exported", "Exported to {file}").format(
                file=fname
            )
            messagebox.showinfo(i18n.get("system.msg.success", "Success"), msg)
        except Exception as e:
            msg = i18n.get(
                "system.msg.export_fail", "Export failed: {error}"
            ).format(error=e)
            messagebox.showerror(i18n.get("status.error", "Error"), msg)
