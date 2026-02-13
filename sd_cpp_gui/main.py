"""
Entry point for the application.
"""
# -----------------------------------------------------------------------------
# NUITKA CONFIGURATION
# -----------------------------------------------------------------------------
# nuitka-project: --output-filename=scg
# nuitka-project: --onefile
# nuitka-project: --standalone
# nuitka-project: --enable-plugin=tk-inter
# nuitka-project: --include-package=sd_cpp_gui.plugins.core_embedding
# nuitka-project: --include-package=sd_cpp_gui.plugins.core_img2img
# nuitka-project: --include-package=sd_cpp_gui.plugins.core_lora
# nuitka-project: --include-package=sd_cpp_gui.plugins.core_networks
# nuitka-project: --include-package=sd_cpp_gui.plugins.core_preview
# nuitka-project: --include-package=sd_cpp_gui.plugins.core_queue
# nuitka-project: --include-package=sd_cpp_gui.plugins.core_remote
# nuitka-project: --include-package=sd_cpp_gui.plugins.core_txt2img
# nuitka-project: --include-package=sd_cpp_gui.plugins.shared_ui
# nuitka-project: --include-package-data=ttkbootstrap
# nuitka-project: --include-data-dir=./data=data
# nuitka-project-if: {OS} == "Windows":
#     nuitka-project: --windows-disable-console
# -----------------------------------------------------------------------------
from PIL import Image

import sd_cpp_gui.ui.components.nine_slices as nine_slices
from sd_cpp_gui.domain.generation.engine import SDRunner
from sd_cpp_gui.domain.generation.server_backend import SDServerRunner
from sd_cpp_gui.infrastructure.di_container import DependencyContainer
from sd_cpp_gui.infrastructure.logger import setup_logging
from sd_cpp_gui.infrastructure.paths import LOGS_DIR
from sd_cpp_gui.ui.app import App


def main() -> None:
    """Initializes all managers and runs the application.

    Logic: Sets up logging, dependencies, configures UI rendering,
    initializes runners, and launches the App."""
    try:
        setup_logging(log_file=LOGS_DIR / "sd_cpp_gui.log")
        container = DependencyContainer()
        ui_scale_str = container.settings.get("ui_scale", "1")
        if ui_scale_str and str(ui_scale_str).isdigit():
            nine_slices.GLOBAL_SCALE = int(ui_scale_str)
        else:
            nine_slices.GLOBAL_SCALE = 1
        _quality_map = {
            "Nearest": Image.Resampling.NEAREST,
            "Bilinear": Image.Resampling.BILINEAR,
            "Bicubic": Image.Resampling.BICUBIC,
            "Lanczos": Image.Resampling.LANCZOS,
        }
        first_quality_str = container.settings.get(
            "ui_first_quality", "Nearest"
        )
        if first_quality_str in _quality_map:
            nine_slices.FIRST_RESAMPLING = _quality_map[first_quality_str]
        last_quality_str = container.settings.get("ui_quality", "Bicubic")
        if last_quality_str in _quality_map:
            nine_slices.LAST_RESAMPLING = _quality_map[last_quality_str]
        executable_path = container.settings.get_app()
        server_executable_path = (
            container.settings.get("server_executable_path", None) or ""
        )
        cli_runner = SDRunner(executable_path)
        server_runner = SDServerRunner(
            server_executable_path,
            container.cmd_loader.flags_mapping,
            container.settings,
        )
        app = App(container, cli_runner, server_runner)
        app.place_window_center()
        app.mainloop()
    except Exception as e:
        import logging

        logging.exception(e)
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Toplevel()
        root.withdraw()
        messagebox.showerror(
            "Application Error", f"An unexpected error occurred: {e}"
        )
        root.destroy()
        raise e


if __name__ == "__main__":
    main()
