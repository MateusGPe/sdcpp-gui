from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.plugins.shared_ui.net_editor import NetworkEditor
from sd_cpp_gui.plugins.shared_ui.network_section_base import NetworkSection
from sd_cpp_gui.plugins.shared_ui.network_widgets import LoraWidget

if TYPE_CHECKING:
    import tkinter as tk

    from sd_cpp_gui.data.db.data_manager import LoraManager
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class LoraSection(NetworkSection):
    def __init__(
        self,
        parent: tk.Widget | tk.Frame,
        lora_manager: LoraManager,
        on_param_change: Optional[Callable[[str, str, Any, bool], None]],
    ) -> None:
        """Logic: Initializes Lora Section."""
        super().__init__(
            parent,
            lora_manager,
            title="LoRA (Low-Rank Adaptation)",
            editor_callback=lambda: NetworkEditor(
                self, lora_manager, self.refresh_list, network_type="lora"
            ),
            widget_class=LoraWidget,
            on_param_change=on_param_change,
        )
