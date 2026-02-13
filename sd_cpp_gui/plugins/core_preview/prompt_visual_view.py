from __future__ import annotations

import tkinter as tk
from typing import Any, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import LEFT, RIGHT

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.ui.components import entry
from sd_cpp_gui.ui.components.color_manager import ColorManager
from sd_cpp_gui.ui.components.draggable_token_list import DraggableTokenList
from sd_cpp_gui.ui.components.utils import CopyLabel


class PromptVisualView(ttk.Frame):
    """View based on the right frame of PromptWindow (Visual Editor)."""

    def __init__(
        self,
        parent: tk.Misc,
        color_manager: ColorManager,
        state_manager: Any,
        autocomplete_service: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.color_manager = color_manager
        self.state_manager = state_manager
        self.autocomplete_service = autocomplete_service
        self.is_syncing = False
        self.current_selection: Optional[tuple[int, str]] = None
        self._debounce_timer: Optional[str] = None
        self.current_mode = "positive"
        self.var_neg = tk.BooleanVar(value=False)
        self._target_list: Optional[DraggableTokenList] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(1, weight=1)

        self.f_toolbar = ttk.Frame(self)
        self.f_toolbar.grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5)
        )

        self.lbl_mode = ttk.Label(
            self.f_toolbar,
            text="Positive Prompt",
            font=(SYSTEM_FONT, 10, "bold"),
            bootstyle="primary",
        )
        self.lbl_mode.pack(side=LEFT)

        self.chk_mode = ttk.Checkbutton(
            self.f_toolbar,
            text="Negative",
            variable=self.var_neg,
            bootstyle="danger-round-toggle",
            command=self._toggle_mode,
        )
        self.chk_mode.pack(side=RIGHT)

        self.main_token_list = DraggableTokenList(
            self,
            separator=",",
            # title="Tags (Comma Separated)",
            on_change=self._on_main_tokens_change,
            on_selection_change=self._on_main_selection_change,
            autocomplete_service=self.autocomplete_service,
            on_background_right_click=lambda e: self._show_context_menu(
                e, self.main_token_list
            ),
        )
        self.main_token_list.grid(
            row=1, column=0, rowspan=3, sticky="nsew", padx=(0, 5)
        )

        self.space_token_list = DraggableTokenList(
            self,
            separator=" ",
            # title="Space Separated (Components)",
            on_change=self._on_selected_token_components_change,
            allow_drag=True,
            autocomplete_service=self.autocomplete_service,
            on_background_right_click=lambda e: self._show_context_menu(
                e, self.space_token_list
            ),
        )
        self.space_token_list.grid(row=1, column=1, sticky="nsew")

        CopyLabel(self, text="Raw Selection", font=(SYSTEM_FONT, 9)).grid(
            row=2, column=1, sticky="ew"
        )

        self.text_var = tk.StringVar()
        self.sub_raw_entry = entry.MEntry(
            self, textvariable=self.text_var, radius=CORNER_RADIUS
        )
        self.sub_raw_entry.grid(row=3, column=1, sticky="ew")
        self.text_var.trace_add("write", self._on_sub_raw_change)

        self._create_context_menu()

    def _create_context_menu(self) -> None:
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="⬅ Align Left", command=lambda: self._set_alignment("left")
        )
        self.context_menu.add_command(
            label="⏺ Align Center",
            command=lambda: self._set_alignment("center"),
        )
        self.context_menu.add_command(
            label="➡ Align Right", command=lambda: self._set_alignment("right")
        )
        self.context_menu.add_command(
            label="≣ Justify", command=lambda: self._set_alignment("justify")
        )
        self.context_menu.add_command(
            label="↔ Fill", command=lambda: self._set_alignment("fill")
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Select All",
            command=lambda: self._perform_selection_action("all"),
        )
        self.context_menu.add_command(
            label="Select None",
            command=lambda: self._perform_selection_action("none"),
        )
        self.context_menu.add_command(
            label="Invert Selection",
            command=lambda: self._perform_selection_action("invert"),
        )

    def _show_context_menu(
        self, event: tk.Event, target: DraggableTokenList
    ) -> None:
        self._target_list = target
        self.context_menu.tk_popup(event.x_root + 1, event.y_root + 1)

    def _set_alignment(self, align: str) -> None:
        if self._target_list:
            self._target_list.set_alignment(align)

    def _perform_selection_action(self, action: str) -> None:
        if not self._target_list:
            return
        if action == "all":
            self._target_list.select_all()
        elif action == "none":
            self._target_list.select_none()
        elif action == "invert":
            self._target_list.invert_selection()

    def _toggle_mode(self) -> None:
        if self.var_neg.get():
            self.current_mode = "negative"
            self.lbl_mode.configure(text="Negative Prompt", bootstyle="danger")
        else:
            self.current_mode = "positive"
            self.lbl_mode.configure(text="Positive Prompt", bootstyle="primary")
        self._refresh_content()

    def _refresh_content(self) -> None:
        if not self.state_manager:
            return
        text = (
            self.state_manager.state.negative_prompt
            if self.current_mode == "negative"
            else self.state_manager.state.prompt
        )
        self.set_text(text)

    def on_show(self) -> None:
        """Logic: Setup listeners and load content."""
        if self.state_manager:
            self.state_manager.add_listener(self._on_state_changed)
            self._refresh_content()

    def on_hide(self) -> None:
        """Logic: Cleanup listeners and content."""
        if self.state_manager:
            self.state_manager.remove_listener(self._on_state_changed)
        self.is_syncing = True
        self.main_token_list.set_tokens([])
        self.space_token_list.set_tokens([])
        self.safe_clear_raw_entry()
        self.is_syncing = False

    def _on_state_changed(self, event_type: str, key: str, value: Any) -> None:
        target_key = (
            "negative_prompt" if self.current_mode == "negative" else "prompt"
        )
        if event_type == "prompt" and key == target_key:
            new_text = str(value)
            # Compare tokens to avoid resetting selection if content is
            # effectively same
            current_tokens = [t.strip() for t in self.main_token_list.tokens]
            new_tokens = [
                t.strip() for t in DraggableTokenList.smart_split(new_text, ",")
            ]
            if current_tokens != new_tokens:
                self.set_text(new_text)

    def _schedule_state_push(self) -> None:
        if self._debounce_timer:
            self.after_cancel(self._debounce_timer)
        self._debounce_timer = self.after(300, self._push_state)

    def safe_clear_raw_entry(self) -> None:
        self.is_syncing = True
        self.current_selection = None
        self.sub_raw_entry.set_text("")
        self.is_syncing = False

    def _push_state(self) -> None:
        tokens = self.main_token_list.tokens
        text = ",".join((t.strip() for t in tokens))
        target_key = (
            "negative_prompt" if self.current_mode == "negative" else "prompt"
        )
        current_val = getattr(self.state_manager.state, target_key)
        if self.state_manager and current_val != text:
            self.state_manager.update_prompt(target_key, text)

    def set_text(self, text: str) -> None:
        self.is_syncing = True
        parts = DraggableTokenList.smart_split(text, ",")
        self.main_token_list.set_tokens(parts)
        self.is_syncing = False
        self._on_main_selection_change(None, "")

    def _on_main_selection_change(
        self, index: Optional[int], text: str
    ) -> None:
        if index is None:
            self.space_token_list.set_tokens([])
            self.safe_clear_raw_entry()
            return

        self.current_selection = (index, text)
        self.is_syncing = True
        sd_tokens = DraggableTokenList.sd_tokenizer(text)
        self.space_token_list.set_tokens(sd_tokens)
        self.sub_raw_entry.set_text(text)
        self.is_syncing = False

    def _on_main_tokens_change(self, tokens: list[str]) -> None:
        if self.is_syncing:
            return
        self._schedule_state_push()

    def _on_selected_token_components_change(self, tokens: list[str]) -> None:
        if self.is_syncing or self.current_selection is None:
            return
        new_text = DraggableTokenList.sd_joiner(tokens)
        self.is_syncing = True
        self.sub_raw_entry.set_text(new_text)
        self.is_syncing = False
        self._update_selected_token(new_text)

    def _on_sub_raw_change(self, *_args: Any) -> None:
        if self.is_syncing or self.current_selection is None:
            return
        new_text = self.sub_raw_entry.get()
        self.is_syncing = True
        sd_tokens = DraggableTokenList.sd_tokenizer(new_text)
        self.space_token_list.set_tokens(sd_tokens)
        self.is_syncing = False
        self._update_selected_token(new_text)

    def _update_selected_token(self, new_text: str) -> None:
        idx, _ = self.current_selection
        if idx < len(self.main_token_list.tokens):
            self.main_token_list.update_token(idx, new_text)
            self.current_selection = (idx, new_text)

    def update_theme(self, side_color: str) -> None:
        self.configure(bootstyle=side_color)
        self.color_manager.bootstyle = side_color
        self.color_manager.update_palette()
        self.main_token_list._update_canvas_style()
        self.space_token_list._update_canvas_style()
