from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.plugins.shared_ui.net_editor import NetworkEditor
from sd_cpp_gui.plugins.shared_ui.network_section_base import NetworkSection
from sd_cpp_gui.plugins.shared_ui.network_widgets import EmbeddingWidget

if TYPE_CHECKING:
    import tkinter as tk

    from sd_cpp_gui.data.db.data_manager import EmbeddingManager
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class EmbeddingSection(NetworkSection):
    """Specific section for Embeddings."""

    def __init__(
        self,
        parent: tk.Widget | tk.Frame,
        embedding_manager: EmbeddingManager,
        on_param_change: Optional[Callable[[str, str, Any, bool], None]] = None,
    ) -> None:
        """Logic: Initializes Embedding Section."""
        super().__init__(
            parent,
            embedding_manager,
            title="Embeddings (Textual Inversion)",
            editor_callback=lambda: NetworkEditor(  # type: ignore
                self,
                embedding_manager,
                self.refresh_list,
                network_type="embedding",
            ),
            widget_class=EmbeddingWidget,
            on_param_change=on_param_change,
        )
