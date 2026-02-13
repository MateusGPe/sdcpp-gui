from typing import Optional
import ttkbootstrap as ttk

from sd_cpp_gui.core.data_manager import EmbeddingManager, LoraManager
from sd_cpp_gui.core.i18n import get_i18n
from sd_cpp_gui.ui.argument_manager import ArgumentManager
from sd_cpp_gui.ui.panels.net_tab.base import NetworkSection
from sd_cpp_gui.ui.panels.net_tab.widgets import EmbeddingWidget, LoraWidget
from sd_cpp_gui.ui.windows.lora_editor import LoraEditorWindow

i18n = get_i18n()


class LoraSection(NetworkSection):
    def __init__(
        self,
        parent,
        lora_manager: LoraManager,
        on_param_change,
        args_manager: ArgumentManager,
    ):
        self.var_add_triggers = ttk.BooleanVar(value=False)
        super().__init__(
            parent,
            lora_manager,
            title="LoRA (Low-Rank Adaptation)",
            editor_callback=lambda: LoraEditorWindow(
                self, lora_manager, self.refresh_list
            ),
            widget_class=LoraWidget,
            on_param_change=on_param_change,
            args_manager=args_manager,
        )

    def _init_ui(self):
        super()._init_ui()
        chk = ttk.Checkbutton(
            self.toolbar,
            variable=self.var_add_triggers,
            text=i18n.get("lora.add_triggers"),
            bootstyle="round-toggle",
        )
        chk.grid(row=1, column=0, columnspan=5, sticky="e", padx=5, pady=5)

    def reset(self):
        """Resets the section and the 'add triggers' checkbox."""
        super().reset()
        self.var_add_triggers.set(False)


class EmbeddingSection(NetworkSection):
    """Specific section for Embeddings."""

    def __init__(
        self,
        parent,
        embedding_manager: EmbeddingManager,
        on_param_change=None,
        args_manager: Optional[ArgumentManager] = None,
    ):
        super().__init__(
            parent,
            embedding_manager,
            title="Embeddings (Textual Inversion)",
            editor_callback=None,  # An editor could be added later to rename aliases
            widget_class=EmbeddingWidget,
            on_param_change=on_param_change,
            args_manager=args_manager,
        )
