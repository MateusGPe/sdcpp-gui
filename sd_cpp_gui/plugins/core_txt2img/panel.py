"""
General Panel (Model Selection and Prompt).
Refactored to use StateManager.
Moved to plugins/core_txt2img.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import LEFT, RIGHT, X
from ttkbootstrap.widgets import ToolTip

from sd_cpp_gui.constants import (
    CORNER_RADIUS,
    EMOJI_FONT,
    MSG_MODEL_SELECTED,
    SYSTEM_FONT,
)
from sd_cpp_gui.infrastructure.di_container import DependencyContainer
from sd_cpp_gui.infrastructure.event_bus import EventBus
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.plugins.shared_ui.model_editor import ModelEditor
from sd_cpp_gui.plugins.shared_ui.quantize_dialog import QuantizeDialog
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.prompt_highlighter import PromptHighlighter
from sd_cpp_gui.ui.components.utils import CopyLabel
from sd_cpp_gui.ui.controls.base import BaseArgumentControl

if TYPE_CHECKING:
    from sd_cpp_gui.data.db.data_manager import ModelManager
    from sd_cpp_gui.domain.generation import StateManager
    from sd_cpp_gui.domain.generation.commands_loader import CommandLoader
    from sd_cpp_gui.domain.services.autocomplete_service import (
        AutocompleteService,
    )
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class GeneralPanel(ttk.Frame):
    """
    General Panel: Model Selection, Prompt, and Dynamic Parameters.
    """

    # pylint: disable=too-many-ancestors, too-many-instance-attributes

    def __init__(
        self,
        parent: tk.Widget,
        container: DependencyContainer = None,
    ) -> None:
        """Logic: Initializes General Panel."""
        super().__init__(parent)
        self._container = container
        self.models: ModelManager = self._container.models
        self.cmd_loader: CommandLoader = self._container.cmd_loader
        self.state_manager: StateManager = self._container.state_manager
        self.autocomplete_service: AutocompleteService = (
            self._container.autocomplete
        )
        self.combo_models: ttk.Combobox
        self.txt_prompt: PromptHighlighter
        self.txt_negative: PromptHighlighter
        self.dynamic_container: ttk.Frame
        self.var_keep_params = tk.BooleanVar(value=False)
        self.list_map: Dict[str, str] = {}
        self.preset_controls: Dict[str, BaseArgumentControl] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        """Logic: Builds UI."""
        f_tools = ttk.Frame(self)
        f_tools.pack(fill=X, pady=(0, 5))
        lbl_base_model = i18n.get("general.lbl.base_model")
        CopyLabel(
            f_tools, text=lbl_base_model, font=(SYSTEM_FONT, 9, "bold")
        ).pack(side=LEFT)
        btn_del = flat.RoundedButton(
            f_tools,
            text="➖",
            command=self._req_delete_model,
            width=40,
            height=40,
            corner_radius=CORNER_RADIUS,
            bootstyle="danger",
            font=(EMOJI_FONT, 12),
        )
        btn_del.pack(side=RIGHT, padx=0)
        ToolTip(
            btn_del, text=i18n.get("general.btn.delete"), bootstyle="danger"
        )
        btn_edit = flat.RoundedButton(
            f_tools,
            text="📝",
            command=self._open_edit_model,
            width=40,
            height=40,
            corner_radius=CORNER_RADIUS,
            bootstyle="warning",
            font=(EMOJI_FONT, 12),
        )
        btn_edit.pack(side=RIGHT, padx=0)
        ToolTip(
            btn_edit, text=i18n.get("general.btn.edit"), bootstyle="warning"
        )
        btn_new = flat.RoundedButton(
            f_tools,
            text="➕",
            command=lambda: ModelEditor(self, self.state_manager.arg_processor),  # type: ignore
            width=40,
            height=40,
            corner_radius=CORNER_RADIUS,
            bootstyle="success",
            font=(EMOJI_FONT, 12),
        )
        btn_new.pack(side=RIGHT, padx=0)
        ToolTip(btn_new, text=i18n.get("general.btn.new"), bootstyle="success")
        btn_quant = flat.RoundedButton(
            f_tools,
            text="🤏",
            command=self._open_quantize_dialog,
            width=40,
            height=40,
            corner_radius=CORNER_RADIUS,
            bootstyle="info",
            font=(EMOJI_FONT, 12),
        )
        btn_quant.pack(side=RIGHT, padx=0)
        ToolTip(btn_quant, text="Quantize to GGUF", bootstyle="info")
        chk_keep_prompt = i18n.get("general.chk.keep_params")
        ttk.Checkbutton(
            f_tools,
            text=chk_keep_prompt,
            variable=self.var_keep_params,
            bootstyle="secondary-round-toggle",
        ).pack(side=RIGHT, padx=(0, 15))
        self.combo_models = ttk.Combobox(
            self, state="readonly", font=(SYSTEM_FONT, 10)
        )
        self.combo_models.pack(fill=X, pady=(0, 15))
        self.combo_models.bind("<<ComboboxSelected>>", self._on_combo_select)
        lbl_positive = i18n.get("general.lbl.positive_prompt")
        f_pos = ttk.Frame(self)
        f_pos.pack(fill=X, pady=(5, 0))
        CopyLabel(
            f_pos, text=lbl_positive, font=(SYSTEM_FONT, 10, "bold")
        ).pack(side=LEFT)
        prompt_cmd = self.cmd_loader.get_by_internal_name("Prompt")
        prompt_flag = prompt_cmd["flag"] if prompt_cmd else "-p"
        self.txt_prompt = PromptHighlighter(
            self,
            name=i18n.get("general.lbl.positive_prompt"),
            flag=prompt_flag,
            height=180,
            wrap="word",
            font=(SYSTEM_FONT, 12),
            autocomplete_service=self.autocomplete_service,
        )
        self.txt_prompt.pack(fill=X, pady=(0, 15))
        lbl_negative = i18n.get("general.lbl.negative_prompt")
        f_neg = ttk.Frame(self)
        f_neg.pack(fill=X, pady=(5, 0))
        CopyLabel(
            f_neg, text=lbl_negative, font=(SYSTEM_FONT, 10, "bold")
        ).pack(side=LEFT)
        neg_cmd = self.cmd_loader.get_by_internal_name("Negative Prompt")
        neg_flag = neg_cmd["flag"] if neg_cmd else "-n"
        self.txt_negative = PromptHighlighter(
            self,
            name=i18n.get("general.lbl.negative_prompt"),
            flag=neg_flag,
            height=120,
            wrap="word",
            font=(SYSTEM_FONT, 10),
            autocomplete_service=self.autocomplete_service,
        )
        self.txt_negative.pack(fill=X, pady=(0, 15))
        self.dynamic_container = ttk.Frame(self)
        self.dynamic_container.pack(fill=X, pady=5)
        self.state_manager.register_control(
            self.txt_prompt.flag, self.txt_prompt, unique=True
        )
        self.state_manager.register_control(
            self.txt_negative.flag, self.txt_negative, unique=True
        )

    def _on_combo_select(self, _event: tk.Event) -> None:
        """Publishes an event on the EventBus when the model changes.

        Logic: Handles model selection."""
        model_id = self.get_selected_model_id()
        if model_id:
            EventBus.publish(MSG_MODEL_SELECTED, model_id)

    def refresh_models_list(self) -> List[str]:
        """Refreshes the list of models in the Combobox.

        Logic: Refreshes models list."""
        models = self.models.get_all()
        names = [m["name"] for m in models]
        self.list_map = {m["name"]: m["id"] for m in models}
        self.combo_models["values"] = names
        return names

    def select_model_by_id(self, model_id: str) -> None:
        """Selects a model via ID programmatically.

        Logic: Selects model by ID."""
        m = self.models.get_model(model_id)
        if m:
            self.combo_models.set(m["name"])
            self._on_combo_select(None)  # type: ignore
        else:
            self.combo_models.set("")

    def get_selected_model_id(self) -> Optional[str]:
        """Returns the ID of the currently selected model.

        Logic: Gets selected model ID."""
        name = self.combo_models.get()
        return self.list_map.get(name)

    def get_prompt(self) -> str:
        """Returns the prompt text.

        Logic: Gets prompt text."""
        return self.txt_prompt.var_value.get().strip()

    def set_prompt(self, text: str) -> None:
        """Sets the prompt text, updating both variable and visual widget.

        Logic: Sets prompt text."""
        self.txt_prompt.var_value.set(text)
        self.txt_prompt.set_text(text)

    def get_negative_prompt(self) -> str:
        """Returns the negative prompt text.

        Logic: Gets negative prompt text."""
        return self.txt_negative.var_value.get().strip()

    def set_negative_prompt(self, text: str) -> None:
        """
        Sets the negative prompt text, updating both variable and visual widget.
        Logic: Sets negative prompt text.
        """
        self.txt_negative.var_value.set(text)
        self.txt_negative.set_text(text)

    def clear_dynamic_params(self) -> None:
        """Removes all dynamic controls.

        Logic: Clears dynamic params."""
        for flag, w in self.preset_controls.items():
            self.state_manager.remove_control(flag, w)
            w.destroy()
        self.preset_controls.clear()

    def add_dynamic_param(self, flag: str, value: Any, enabled: bool) -> None:
        """Logic: Adds dynamic param."""
        ctrl = self.state_manager.new_argument_control(
            self.dynamic_container, flag
        )
        if ctrl:
            ctrl.pack(fill=X, expand=True, pady=2)
            ctrl.set_value(value)
            ctrl.var_enabled.set(enabled)
            ctrl.toggle_state()
            self.preset_controls[flag] = ctrl

    def _open_edit_model(self) -> None:
        """Logic: Opens edit model window."""
        model_id = self.get_selected_model_id()
        if not model_id:
            messagebox.showwarning(
                i18n.get("msg.warning"), i18n.get("msg.select_model_edit")
            )
            return
        model_data = self.models.get_model(model_id)
        if model_data:
            ModelEditor(self, self.state_manager.arg_processor, model_data)

    def _open_quantize_dialog(self) -> None:
        """Logic: Opens quantization dialog."""
        model_id = self.get_selected_model_id()
        if not model_id:
            messagebox.showwarning(
                i18n.get("msg.warning"), "Please select a model to quantize."
            )
            return
        model_data = self.models.get_model(model_id)
        if model_data:
            QuantizeDialog(
                self,
                model_manager=self.models,
                settings_manager=self._container.settings,
                model_data=model_data,
            )

    def _req_delete_model(self) -> None:
        """Logic: Requests delete model."""
        name = self.combo_models.get()
        if not name:
            return
        title = i18n.get("general.msg.confirm_title")
        msg = i18n.get("general.msg.confirm_delete").format(name=name)
        if messagebox.askyesno(title, msg):
            lid = self.list_map.get(name)
            if lid:
                self.models.delete_model(lid)
                self.refresh_models_list()
                self.combo_models.set("")
                self.clear_dynamic_params()

    def reset(self) -> None:
        """Resets prompts and dynamic controls if 'Keep parameters' is off.

        Logic: Resets panel."""
        if not self.var_keep_params.get():
            self.state_manager.update_prompt("prompt", "")
            self.state_manager.update_prompt("negative_prompt", "")
            self.clear_dynamic_params()
