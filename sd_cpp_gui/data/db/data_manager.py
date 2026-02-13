"""
Data Manager - re-exports from the db package.
"""

# Re-export database and manager classes for easy access
from sd_cpp_gui.constants import CORNER_RADIUS
from sd_cpp_gui.data.db.history_manager import HistoryManager
from sd_cpp_gui.data.db.init_db import Database
from sd_cpp_gui.data.db.model_manager import ModelManager
from sd_cpp_gui.data.db.network_manager import EmbeddingManager, LoraManager
from sd_cpp_gui.data.db.queue_manager import QueueManager
from sd_cpp_gui.data.db.settings_manager import SettingsManager
from sd_cpp_gui.data.remote.remote_manager import RemoteManager

# Initialize the database on import
Database()

__all__ = [
    "Database",
    "SettingsManager",
    "ModelManager",
    "LoraManager",
    "EmbeddingManager",
    "HistoryManager",
    "QueueManager",
    "RemoteManager",
]

# Testing block
if __name__ == "__main__":
    import tkinter as tk
    from tkinter import filedialog, messagebox

    from sd_cpp_gui.infrastructure.logger import get_logger
    from sd_cpp_gui.infrastructure.paths import OUTPUT_DIR
    from sd_cpp_gui.ui.components import flat

    try:
        from openpyxl.utils.exceptions import InvalidFileException

        HAS_OPENPYXL = True
    except ImportError:
        HAS_OPENPYXL = False
        InvalidFileException = Exception  # type: ignore

    logger = get_logger(__name__)

    def main_gui() -> None:
        """Runs the test GUI."""
        root = tk.Toplevel()
        root.withdraw()  # Hide the main window
        root.title("Data Manager")

        m_manager = ModelManager()

        def ask_export():
            """Exports models via file dialog."""
            filetypes = [
                ("JSON Files", "*.json"),
                ("CSV Files", "*.csv"),
                ("Excel Files", "*.xlsx"),
            ]
            if not HAS_OPENPYXL:
                filetypes.pop()

            filename = filedialog.asksaveasfilename(
                title="Export Models",
                initialdir=str(OUTPUT_DIR),
                filetypes=filetypes,
                defaultextension=".json",
            )

            if not filename:
                return

            try:
                if filename.endswith(".json"):
                    m_manager.export_to_json(filename)
                elif filename.endswith(".csv"):
                    m_manager.export_to_csv(filename)
                elif filename.endswith(".xlsx"):
                    m_manager.export_to_xlsx(filename)
                else:
                    messagebox.showerror("Error", "Unsupported format.")
                    return
                messagebox.showinfo(
                    "Success", f"Successfully exported to:\n{filename}"
                )
            except (IOError, InvalidFileException) as e:
                messagebox.showerror("Error", f"Export failed:\n{str(e)}")

        def ask_import():
            """Imports models via file dialog."""
            filetypes = [
                ("All Supported", "*.json *.csv *.xlsx"),
                ("JSON Files", "*.json"),
                ("CSV Files", "*.csv"),
                ("Excel Files", "*.xlsx"),
            ]
            if not HAS_OPENPYXL:
                filetypes = [
                    ("All Supported", "*.json *.csv"),
                    ("JSON Files", "*.json"),
                    ("CSV Files", "*.csv"),
                ]

            filename = filedialog.askopenfilename(
                title="Import Models",
                initialdir=str(OUTPUT_DIR),
                filetypes=filetypes,
            )

            if not filename:
                return

            try:
                if filename.endswith(".json"):
                    m_manager.import_from_json(filename)
                elif filename.endswith(".csv"):
                    m_manager.import_from_csv(filename)
                elif filename.endswith(".xlsx"):
                    m_manager.import_from_xlsx(filename)
                else:
                    messagebox.showerror("Error", "Unknown format.")
                    return
                messagebox.showinfo(
                    "Success", "Import complete! Data updated in the database."
                )
            except (IOError, InvalidFileException) as e:
                messagebox.showerror("Error", f"Import failed:\n{str(e)}")

        # Create the test GUI window
        menu_window = tk.Toplevel(root)
        menu_window.title("Data Menu")
        menu_window.geometry("300x180")
        menu_window.protocol("WM_DELETE_WINDOW", root.destroy)

        tk.Label(
            menu_window, text="Model Manager", font=("Arial", 12, "bold")
        ).pack(pady=10)

        flat.RoundedButton(
            menu_window,
            text="\ud83d\udcbe Export Models",
            command=ask_export,
            height=40,
            corner_radius=CORNER_RADIUS,
            elevation=1,
        ).pack(pady=5)
        flat.RoundedButton(
            menu_window,
            text="\ud83d\udcbe Import Models",
            command=ask_import,
            height=40,
            corner_radius=CORNER_RADIUS,
            elevation=1,
        ).pack(pady=5)

        if not HAS_OPENPYXL:
            tk.Label(
                menu_window,
                text="(Excel disabled: install openpyxl)",
                fg="red",
                font=("Arial", 8),
            ).pack()

        root.mainloop()

    logger.info("=== Data Manager: GUI Mode Initiated ===")
    main_gui()
