"""
Dialog for quantizing models (safetensors/ckpt -> gguf).
"""

import os
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Optional

import ttkbootstrap as ttk
from rapidfuzz import fuzz
from ttkbootstrap.constants import BOTH, END, RIGHT, X
from ttkbootstrap.scrolled import ScrolledText

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.data.db.model_manager import ModelManager
from sd_cpp_gui.data.db.models import ModelData
from sd_cpp_gui.data.db.settings_manager import SettingsManager
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import flat

i18n = get_i18n()

quantization_types = [
    "bf16",
    "f16",
    "f32",
    "f64",
    "i16",
    "i32",
    "i64",
    "i8",
    "iq1_m",
    "iq1_s",
    "iq2_s",
    "iq2_xs",
    "iq2_xxs",
    "iq3_s",
    "iq3_xxs",
    "iq4_nl",
    "iq4_xs",
    "mxfp4",
    "q2_K",
    "q3_K",
    "q4_0",
    "q4_1",
    "q4_K",
    "q5_0",
    "q5_1",
    "q5_K",
    "q6_K",
    "q8_0",
    "q8_1",
    "q8_K",
    "tq1_0",
    "tq2_0",
]


class QuantizeRunner:
    """
    Runner for the quantization process, modeled after SDRunner.
    """

    def __init__(self, executable_path: str) -> None:
        """Initializes the runner with the executable path."""
        self.executable_path = executable_path
        self.process: Optional[subprocess.Popen] = None

    def run(
        self,
        input_path: str,
        output_path: str,
        q_type: str,
        on_log: Callable[[str], None],
        on_finish: Callable[[bool], None],
    ) -> None:
        """Executes the quantization command in a separate thread."""

        def _worker() -> None:
            cmd = [
                self.executable_path,
                "-M",
                "convert",
                "-m",
                input_path,
                "-o",
                output_path,
                "-v",
                "--type",
                q_type,
            ]
            on_log(f"CMD: {' '.join(cmd)}\n{'=' * 40}\n")

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()  # type: ignore
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    startupinfo=startupinfo,
                )
                if self.process.stdout:
                    for line in iter(self.process.stdout.readline, ""):
                        on_log(line)
                rc = self.process.wait()
                on_finish(rc == 0)
            except (OSError, RuntimeError) as err:
                on_log(f"FATAL ERROR: {err}\n")
                on_finish(False)

        threading.Thread(target=_worker, daemon=True).start()

    def stop(self) -> None:
        """Stops the process if running."""
        if self.process:
            try:
                self.process.terminate()
            except OSError:
                pass


class QuantizeDialog(ttk.Toplevel):
    """
    Dialog to convert models to GGUF format with automatic folder
    creation and DB registration.
    """

    def __init__(
        self,
        parent: tk.Widget,
        model_manager: ModelManager,
        settings_manager: SettingsManager,
        model_data: ModelData,
    ) -> None:
        """
        Initializes the dialog with the target model data.
        """
        super().__init__(parent)
        self.title("Quantize Model (safetensors -> gguf)")
        self.geometry("700x600")

        self.model_manager = model_manager
        self.settings_manager = settings_manager
        self.model_data = model_data

        self.runner: Optional[QuantizeRunner] = None
        self.is_running = False

        self._init_ui()
        self._center_window()

    def _init_ui(self) -> None:
        """Builds the UI components."""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        # Header Info
        info_frame = ttk.Labelframe(
            main_frame, text="Current Model", padding=10
        )
        info_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(
            info_frame,
            text=f"Name: {self.model_data.get('name', 'Unknown')}",
            font=(SYSTEM_FONT, 10, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=f"Path: {self.model_data.get('path', 'Unknown')}",
            font=(SYSTEM_FONT, 9),
            bootstyle="secondary",
        ).pack(anchor="w")

        # Quantization Type
        lbl_type = ttk.Label(
            main_frame,
            text="Quantization Type:",
            font=(SYSTEM_FONT, 10, "bold"),
        )
        lbl_type.pack(fill=X, pady=(10, 2))
        self.combo_type = ttk.Combobox(
            main_frame,
            values=quantization_types,
            state="readonly",
        )
        self.combo_type.set("q4_0")
        self.combo_type.pack(fill=X)

        # Logs
        lbl_logs = ttk.Label(
            main_frame, text="Logs:", font=(SYSTEM_FONT, 10, "bold")
        )
        lbl_logs.pack(fill=X, pady=(10, 2))
        self.txt_logs = ScrolledText(main_frame, height=10, autohide=True)
        self.txt_logs.pack(fill=BOTH, expand=True, pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=X, pady=5)

        self.btn_run = flat.RoundedButton(
            btn_frame,
            text="Start Quantization",
            command=self._start_quantization,
            bootstyle="success",
            corner_radius=CORNER_RADIUS,
        )
        self.btn_run.pack(side=RIGHT, padx=5)

        btn_close = flat.RoundedButton(
            btn_frame,
            text="Close",
            command=self.destroy,
            bootstyle="secondary",
            corner_radius=CORNER_RADIUS,
        )
        btn_close.pack(side=RIGHT, padx=5)

    def _start_quantization(self) -> None:
        """
        Logic: Prepares paths, creates new folder, and starts the runner.
        """
        if self.is_running:
            return

        # Retrieve executable using the SettingsManager provided reference
        exe = self.settings_manager.get_app()
        src_path = self.model_data.get("path", "")
        qtype = self.combo_type.get()

        if not exe or not src_path or not os.path.exists(src_path):
            messagebox.showerror(
                "Error", "Invalid model path or executable configuration."
            )
            return

        # Prepare paths
        # Source: /models/checkpoints/my_model.safetensors
        # Target Folder: /models/checkpoints/my_model-q4_0/
        # Target File: /models/checkpoints/my_model-q4_0/my_model-q4_0.gguf

        src_p = Path(src_path)
        src_name_no_ext = src_p.stem
        if (
            fuzz.partial_ratio(
                src_name_no_ext.lower(), src_p.parent.name.lower()
            )
            > 80
        ):
            src_dir = str(src_p.parent.parent)
        else:
            src_dir = str(src_p.parent)

        new_folder_name = f"{src_name_no_ext}-{qtype}"
        target_dir = str(Path(src_dir) / new_folder_name)

        output_filename = f"{src_name_no_ext}-{qtype}.gguf"
        target_path = str(Path(target_dir) / output_filename)

        # UI Update
        self.is_running = True
        self.btn_run.configure(state="disabled", text="Running...")
        self.txt_logs.delete("1.0", END)
        self._append_log(
            f"Executable: {exe}\nSource: {src_path}\nTarget: {target_path}\n"
        )

        try:
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
                self._append_log(f"Created directory: {target_dir}\n")
        except Exception as e:
            self._append_log(f"Error creating directory: {e}\n")
            self._reset_ui_state()
            return

        self.runner = QuantizeRunner(exe)
        # Pass context needed for finish callback
        self.runner.run(
            src_path,
            target_path,
            qtype,
            self._append_log,
            lambda success: self._on_finish(
                success, src_path, target_path, qtype
            ),
        )

    def _on_finish(
        self, success: bool, src_path: str, target_path: str, qtype: str
    ) -> None:
        """
        Logic: Handles post-quantization tasks (sidecar copy, DB update).
        """
        if success:
            self._append_log("Quantization successful.\n")
            self._copy_sidecars(src_path, target_path, qtype)
            self._register_new_model(target_path, qtype)
            messagebox.showinfo(
                "Success",
                f"Model quantized and registered as '{qtype}' variant.",
                parent=self,
            )
        else:
            messagebox.showerror(
                "Error", "Quantization failed. Check logs.", parent=self
            )

        self._reset_ui_state()

    def _reset_ui_state(self) -> None:
        """Logic: Resets buttons and flags."""
        self.is_running = False
        self.after(
            0,
            lambda: self.btn_run.configure(
                state="normal", text="Start Quantization"
            ),
        )

    def _copy_sidecars(
        self, src_path: str, target_path: str, qtype: str
    ) -> None:
        """
        Logic: Copies/Renames sidecars.
        Rule: src_basename.* -> target_basename.*
        """
        src_dir = os.path.dirname(src_path)
        src_basename = os.path.splitext(os.path.basename(src_path))[0]

        dest_dir = os.path.dirname(target_path)
        dest_basename = os.path.splitext(os.path.basename(target_path))[0]

        self._append_log("Processing sidecars...\n")

        try:
            for filename in os.listdir(src_dir):
                # Check if file belongs to the source model
                if filename.startswith(
                    src_basename
                ) and filename != os.path.basename(src_path):
                    # Extract suffix (e.g., .preview.png or .json)
                    suffix = filename[len(src_basename) :]

                    src_file = os.path.join(src_dir, filename)
                    dest_file = os.path.join(dest_dir, dest_basename + suffix)

                    if os.path.isfile(src_file):
                        shutil.copy2(src_file, dest_file)
                        self._append_log(
                            f"Copied: {filename} -> "
                            f"{os.path.basename(dest_file)}\n"
                        )
        except Exception as e:
            self._append_log(f"Sidecar error: {e}\n")

    def _register_new_model(self, new_path: str, qtype: str) -> None:
        """
        Logic: Clones the DB entry pointing to the new file.
        """
        original_name = self.model_data.get("name", "Unknown")
        new_name = f"{original_name} {qtype}"
        params = self.model_data.get("params", [])
        base_model = self.model_data.get("base_model")

        try:
            self.model_manager.add_or_update_model(
                model_id=None,  # New entry
                name=new_name,
                path=new_path,
                params=params,
                base_model=base_model,
            )
            self._append_log(f"Registered in Database: {new_name}\n")
        except Exception as e:
            self._append_log(f"Database error: {e}\n")

    def _append_log(self, text: str) -> None:
        """Appends text to the log widget safely."""
        self.after(0, lambda: self.txt_logs.insert(END, text))
        self.after(0, lambda: self.txt_logs.see(END))

    def _center_window(self) -> None:
        """Centers the window on the screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
