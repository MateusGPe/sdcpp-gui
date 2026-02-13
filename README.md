# SD CPP GUI

A modular and robust Graphical User Interface for Stable Diffusion workflows, designed with extensibility and library management in mind.

## ⚠️ Disclaimer & Project Status

This project is currently a **personal hobby** endeavor and serves primarily as a **technical playground**. It is designed as a sandbox for experimenting with modular architecture, dependency injection, and Tkinter UI patterns within the context of Stable Diffusion.

While it aims to provide a robust toolset for Stable Diffusion workflows, please be aware of the following:

- **Experimental Nature**: The codebase is a testing ground for new ideas. Features may be implemented, refactored, or removed purely for educational purposes or architectural exploration.
- **Work in Progress**: Features may be incomplete or subject to breaking changes without notice.
- **Stability**: You may encounter bugs, UI glitches, or crashes. It is recommended to backup your data (especially the database) regularly.
- **Support**: As a hobby project, immediate support or bug fixes cannot be guaranteed.
- **Performance**: Some operations might not yet be fully optimized.

Use this software at your own risk. Feedback and contributions are welcome!

## Overview

`sd-cpp-gui` provides a Python/Tkinter-based frontend that simplifies the management of Stable Diffusion assets (LoRAs, Embeddings) and generation history. It features a powerful maintenance engine to keep your library organized and your history consistent.

## Key Features

### 🧩 Modular Plugin Architecture
The application is built around the `IPlugin` interface, allowing developers to decouple new features from the core application logic.
- **Extensible UI**: Plugins can inject their own tabs and widgets.
- **Dependency Injection**: Access core services (Settings, EventBus) via the `DependencyContainer`.

### 🧹 Library Maintenance & Sanitization
Keep your model library clean without breaking your history. The `LibraryCleanerService` offers:
- **Automated Renaming**: Scans for non-portable filenames and suggests sanitized versions.
- **Sidecar Handling**: Automatically renames associated files (`.preview.png`, `.json`, `.civitai.info`, etc.) when a model is renamed.
- **Metadata Patching**: Updates internal JSON metadata to match new filenames.

### 📜 Smart History Migration
Renaming a LoRA usually breaks the prompts in your generation history. `sd-cpp-gui` solves this:
- **Prompt Patching**: Automatically updates `<lora:Name:1.0>` tags and embedding triggers in your history database when files are renamed.
- **Missing Network Resolution**: Scans history for missing resources and helps map them to existing files in your library.

## Development

### Project Structure

- `sd_cpp_gui/domain/plugins/`: Contains the plugin interfaces.
- `sd_cpp_gui/domain/maintenance/`: Contains logic for library cleaning and history migration.
- `sd_cpp_gui/data/`: Database and file management layers.

### Implementing a Plugin

To add new functionality, implement the `IPlugin` abstract base class:

```python
from sd_cpp_gui.domain.plugins.interface import IPlugin
import tkinter as tk

class MyCustomPlugin(IPlugin):
    @property
    def manifest(self):
        return {
            "name": "My Custom Plugin",
            "version": "0.1.0",
            "description": "Adds cool new features",
            "key": "my_custom_plugin"
        }

    def initialize(self, container):
        # Retrieve dependencies
        self.settings = container.get("Settings")

    def create_ui(self, parent: tk.Widget):
        # Return a widget to be displayed in the app
        frame = tk.Frame(parent)
        tk.Label(frame, text="Plugin Active").pack()
        return frame
```

## Installation

1. Clone the repository.
2. Install dependencies (ensure you have a Python environment ready):
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python -m sd_cpp_gui.main
   ```

## License

MIT