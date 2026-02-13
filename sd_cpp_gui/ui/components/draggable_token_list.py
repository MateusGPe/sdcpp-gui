"""
Draggable Token List Component.
Refactored to follow SRP and SoC.
"""

from __future__ import annotations

import re
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from ttkbootstrap.publisher import Channel, Publisher

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.ui.components import entry
from sd_cpp_gui.ui.components.color_manager import ColorManager
from sd_cpp_gui.ui.components.command_bar.suggestion_popup import (
    SuggestionPopup,
)
from sd_cpp_gui.ui.components.nine_slices import NineSliceRenderer
from sd_cpp_gui.ui.components.token_context_menu import TokenContextMenu
from sd_cpp_gui.ui.components.token_list_model import TokenListModel
from sd_cpp_gui.ui.components.token_list_view import TokenListView
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.domain.services.autocomplete_service import (
        AutocompleteService,
    )


class DraggableTokenList(tk.Frame):
    """
    A container for TokenChips that supports Drag-and-Drop reordering
    and specific separators.
    """

    def __init__(
        self,
        parent: tk.Misc,
        separator: str = ", ",
        on_change: Optional[Callable[[List[str]], None]] = None,
        on_selection_change: Optional[
            Callable[[Optional[int], str], None]
        ] = None,
        title: Optional[str] = None,
        allow_drag: bool = True,
        autocomplete_service: Optional[AutocompleteService] = None,
        allow_multi_selection: bool = True,
        on_right_click: Optional[Callable[[int, tk.Event], None]] = None,
        on_double_click: Optional[Callable[[int, tk.Event], None]] = None,
        on_scroll_event: Optional[Callable[[int, int, tk.Event], None]] = None,
        on_background_right_click: Optional[Callable[[tk.Event], None]] = None,
        alignment: str = "left",
    ) -> None:
        """
        Initializes the draggable token list.
        """
        super().__init__(parent, bd=0, highlightthickness=0)  # type: ignore
        self.separator = separator
        self.model = TokenListModel(on_change, on_selection_change)
        self.alignment = alignment
        self.autocomplete_service = autocomplete_service
        self.suggestion_popup: Optional[SuggestionPopup] = None
        self.lbl: Optional[CopyLabel] = None
        self._ac_job: Optional[str] = None
        self._ac_loading_more = False
        self.cm = ColorManager(parent, {})
        self.cm.update_palette()
        self.context_menu_handler = TokenContextMenu(self)

        # UI Setup
        self.configure(bg=self.cm.palette.get("parent", "#2b2b2b"))
        self._init_header(title)

        # Canvas wrapper for NineSlice
        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0, height=80)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", lambda _: self.entry.focus())

        self.container_renderer = NineSliceRenderer(
            radius=CORNER_RADIUS, border_width=1, elevation=1
        )
        self._draw_job: Optional[str] = None

        if on_right_click is None:
            on_right_click = self._default_on_right_click

        self.view = TokenListView(
            self.canvas,
            self.model,
            self.cm,
            lambda: self.entry.focus(),
            allow_drag,
            allow_multi_selection,
            on_right_click,
            on_double_click,
            on_scroll_event,
            on_background_right_click,
            alignment=alignment,
            autocomplete_service=autocomplete_service,
        )
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Input Entry
        self.var_entry = tk.StringVar()
        self.entry = entry.MEntry(
            self,
            textvariable=self.var_entry,
            radius=CORNER_RADIUS,
            height=40,
            bootstyle="success",
        )
        self.entry.pack(fill=tk.X, pady=(5, 0))
        self.entry.bind("<Return>", self._on_enter_pressed)
        self.entry.bind("<BackSpace>", self._on_entry_backspace)
        self.entry.bind("<Delete>", self._on_entry_delete)
        self.entry.bind("<Left>", self._on_entry_left)
        self.entry.bind("<Right>", self._on_entry_right)

        if self.autocomplete_service:
            self.entry.bind("<KeyRelease>", self._on_key_release_ac, add="+")
            self.entry.bind("<Up>", self._on_up_ac)
            self.entry.bind("<Down>", self._on_down_ac)
            self.entry.bind("<Tab>", self._on_tab_ac)
            self.entry.bind("<Escape>", self._on_escape_ac)
            self.entry.bind("<FocusOut>", self._on_focus_out_ac, add="+")

        self._update_canvas_style()

        Publisher.subscribe(
            name=str(id(self)), func=self.on_theme_change, channel=Channel.STD
        )

    def set_alignment(self, alignment: str) -> None:
        self.alignment = alignment
        self.view.set_alignment(alignment)

    @property
    def tokens(self) -> List[str]:
        return self.model.tokens

    def _init_header(self, title: str) -> None:
        """
        Builds optional header.
        """
        if title:
            lbl = CopyLabel(
                self,
                text=title,
                font=(SYSTEM_FONT, 9, "bold"),
                bootstyle="secondary",
            )
            lbl.pack(anchor="w", pady=(0, 5))

    def on_theme_change(self, _note: Any = None) -> None:
        """
        Callback: Theme change.
        Updates colors.
        """
        if not self.winfo_exists():
            Publisher.unsubscribe(str(id(self)))
            return
        self._update_canvas_style()

    @staticmethod
    def smart_split(text: str, separator: str = ",") -> List[str]:
        """
        Splits text by separator, respecting brackets (), [], {}, <>.
        Returns: List of tokens.
        """
        if not text:
            return []

        sep_char = separator
        if len(separator) > 1:
            s = separator.strip()
            if s:
                sep_char = s[0]
            else:
                sep_char = separator[0]

        tokens = []
        current = []

        brackets = {"(": ")", "[": "]", "{": "}", "<": ">", '"': '"'}
        closing = {v: k for k, v in brackets.items()}
        stack = []

        for char in text:
            if char in brackets and char in closing:
                if stack and stack[-1] == char:
                    stack.pop()
                else:
                    stack.append(brackets[char])
                current.append(char)
            elif char in brackets:
                stack.append(brackets[char])
                current.append(char)
            elif char in closing:
                if stack and stack[-1] == char:
                    stack.pop()
                current.append(char)
            elif char == sep_char and not stack:
                val = "".join(current).strip()
                if val:
                    tokens.append(val)
                current = []
            else:
                current.append(char)

        val = "".join(current).strip()
        if val:
            tokens.append(val)

        return tokens

    @staticmethod
    def sd_tokenizer(text: str) -> List[str]:
        """
        Splits text into Stable Diffusion tokens (words, numbers, brackets).
        Returns: List of tokens.
        """
        if not text:
            return []
        # This regex finds:
        # - brackets: (), [], <>
        # - colon: :
        # - comma: ,
        # - words: sequences of letters, numbers, underscore, hyphen, dot
        tokens = re.findall(r"\(|\)|\[|\]|<|>|\"|:|,|[^()\[\]<>:,\"\s]+", text)
        return [t.strip() for t in tokens if t.strip()]

    @staticmethod
    def sd_joiner(tokens: List[str]) -> str:
        """
        Joins a list of SD tokens back into a string with proper spacing.
        Returns: Joined string.
        """
        if not tokens:
            return ""

        result = ""
        for i, token in enumerate(tokens):
            # Add space before token if it's not the first,
            # and the previous token is not an opening bracket or separator,
            # and the current token is not a closing bracket or separator.
            if i > 0 and tokens[i - 1] not in '([<:"' and token not in '")]>:,':
                result += " "
            result += token
        return result

    @staticmethod
    def get_token_variant(token: str) -> str:
        """
        Determines the visual variant for a token.
        Returns: variant name.
        """
        if not token:
            return "default"

        # This logic is for compound tokens that haven't been broken down yet.
        if len(token) > 1:
            if (token.startswith("(") and token.endswith(")")) or (
                token.startswith("[") and token.endswith("]")
            ):
                return "special"
            if token.startswith("<") and token.endswith(">"):
                return "special"
            if token.startswith('"') and token.endswith('"'):
                return "special"

        # This logic is for fine-grained, pre-tokenized parts.
        if token in '()[]<>"':
            return "bracket"
        if token in ":,":
            return "separator"

        # Check if it's a number (integer or float)
        if token and (token.startswith(("-", ".")) or token[0].isdigit()):
            try:
                # Ensure it's not just a dot or a hyphen
                if token not in ("-", "."):
                    float(token)
                    return "number"
            except ValueError:
                pass  # Not a valid number, continue to default

        return "default"

    def _on_canvas_resize(self, event: tk.Event) -> None:
        """
        Callback: Canvas resize.
        Schedules redraw.
        """
        self._schedule_redraw()

    def _schedule_redraw(self) -> None:
        """
        Debounces redraw.
        """
        if self._draw_job:
            self.after_cancel(self._draw_job)
        self._draw_job = self.after(10, self._redraw_canvas)

    def _redraw_canvas(self) -> None:
        """
        Draws the nine-slice background.
        """
        if self._draw_job:
            self.after_cancel(self._draw_job)
            self._draw_job = None
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w > 1 and h > 1:
            self.container_renderer.draw_on_canvas(self.canvas, w, h)

    def _on_entry_backspace(self, event: tk.Event) -> Optional[str]:
        """
        Handles Backspace in entry to delete chips.
        """
        if self.entry.selection_present():
            return None

        if self.entry.index(tk.INSERT) == 0:
            if self.model._selected_indices:
                self.model.delete_selected()
                self.view.sync_chips()
            elif self.model.tokens:
                # Standard behavior: First backspace selects last token,
                # second deletes it
                last_idx = len(self.model.tokens) - 1
                if (
                    self.model._anchor_index == last_idx
                    and last_idx in self.model._selected_indices
                ):
                    self.model.remove_token(last_idx)
                    self.view.sync_chips()
                else:
                    self.model.select(last_idx)
                    self.view.sync_chips()
            return "break"
        return None

    def _on_entry_delete(self, event: tk.Event) -> Optional[str]:
        """
        Handles Delete key to remove selected chips.
        """
        if self.model._selected_indices:
            self.model.delete_selected()
            self.view.sync_chips()
            return "break"
        return None

    def _on_entry_left(self, event: tk.Event) -> Optional[str]:
        """
        Handles Left Arrow for navigation.
        """
        if (
            self.entry.index(tk.INSERT) == 0
            and not self.entry.selection_present()
        ):
            if not self.model._selected_indices:
                if self.model.tokens:
                    self.model.select(len(self.model.tokens) - 1)
                    self.view.sync_chips()
            else:
                curr = (
                    self.model._anchor_index
                    if self.model._anchor_index is not None
                    else max(self.model._selected_indices)
                )
                new_idx = max(0, curr - 1)
                self.model.select(new_idx)
                self.view.sync_chips()
            return "break"
        return None

    def _on_entry_right(self, event: tk.Event) -> Optional[str]:
        """
        Handles Right Arrow for navigation.
        """
        if self.model._selected_indices:
            curr = (
                self.model._anchor_index
                if self.model._anchor_index is not None
                else min(self.model._selected_indices)
            )
            new_idx = curr + 1
            if new_idx < len(self.model.tokens):
                self.model.select(new_idx)
                self.view.sync_chips()
            else:
                # Deselect and focus entry
                self.model.clear_selection()
                self.view.sync_chips()
                self.entry.icursor(0)
            return "break"
        return None

    def _update_canvas_style(self) -> None:
        """
        Updates colors for the container.
        """
        colors = self.cm.update_palette()
        self.configure(bg=colors["parent"])
        self.canvas.configure(bg=colors["parent"])
        self.view.update_style()
        self.container_renderer.generate_slices(colors)
        self._redraw_canvas()

    def set_tokens(self, tokens: List[str]) -> None:
        """
        Replaces current tokens and rebuilds UI.
        """
        # Filter empty
        if self.model.set_tokens(tokens):
            self.view.sync_chips()

    def get_text(self) -> str:
        """
        Returns joined text.
        """
        return self.separator.join(self.model.tokens)

    def _on_enter_pressed(self, _event: tk.Event) -> Optional[str]:
        """
        Callback: Enter key.
        Adds new token from entry.
        """
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            self.suggestion_popup._confirm_selection()
            return "break"

        text = self.var_entry.get().strip()
        if text:
            new_tokens = self.smart_split(text, self.separator)
            self.model.add_tokens(new_tokens)

            self.var_entry.set("")
            self.view.sync_chips()
        return "break"

    def _rebuild_chips(self) -> None:
        """
        Deprecated alias for _sync_chips_state.
        Kept for compatibility with external plugins.
        """
        self.view.sync_chips()

    def insert_token(self, index: int, text: str) -> None:
        self.model.insert_token(index, text)
        self.view.sync_chips()

    def update_token(self, index: int, text: str) -> None:
        self.model.update_token(index, text)
        self.view.sync_chips()

    def remove_token(self, index: int) -> None:
        self.model.remove_token(index)
        self.view.sync_chips()

    def select_all(self) -> None:
        self.model.select_all()
        self.view.sync_chips()

    def select_none(self) -> None:
        self.model.clear_selection()
        self.view.sync_chips()

    def invert_selection(self) -> None:
        self.model.invert_selection()
        self.view.sync_chips()

    def _on_key_release_ac(self, event: tk.Event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape"):
            return
        if self._ac_job:
            self.after_cancel(self._ac_job)
        self._ac_job = self.after(100, self._trigger_autocomplete)

    def _trigger_autocomplete(
        self, limit: int = 10, initial_index: int = 0
    ) -> None:
        if not self.autocomplete_service:
            return

        full_text = self.var_entry.get()
        cursor_index = self.entry.index(tk.INSERT)
        text_before = full_text[:cursor_index]

        if not text_before.strip():
            self._hide_popup()
            return

        parts = re.split(r"[\s<>()\{\}\[\],\.]", text_before)
        fragment = parts[-1]

        if len(fragment) < 2:
            self._hide_popup()
            return

        results = self.autocomplete_service.search(text_before, limit=limit)
        if not results:
            self._hide_popup()
            return

        pos = self.entry.get_current_word_pos()
        if not pos:
            return
        root_x, root_y = pos

        popup_items = [(r[0], r[4]) for r in results]

        if not self.suggestion_popup:
            self.suggestion_popup = SuggestionPopup(
                self, self._on_suggestion_selected, self.cm
            )

        self.suggestion_popup.show(
            root_x,
            root_y,
            300,
            popup_items,
            autolayout=False,
            initial_index=initial_index,
        )
        self._ac_loading_more = False

    def _on_suggestion_selected(self, text: str) -> None:
        full_text = self.var_entry.get()
        cursor_index = self.entry.index(tk.INSERT)
        text_before = full_text[:cursor_index]
        text_after = full_text[cursor_index:]

        parts = re.split(r"[\s<>()\{\}\[\],\.]", text_before)
        fragment = parts[-1]

        new_text_before = text_before[: -len(fragment)] + text
        self.var_entry.set(new_text_before + text_after)
        self.entry.icursor(len(new_text_before))
        self._hide_popup()

    def _hide_popup(self) -> None:
        if self.suggestion_popup:
            self.suggestion_popup.hide()

    def _on_up_ac(self, _event: tk.Event) -> str:
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            self.suggestion_popup.move_selection(-1)
            return "break"
        return ""

    def _on_down_ac(self, _event: tk.Event) -> str:
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            if self._ac_loading_more:
                return "break"
            (index, max_index) = self.suggestion_popup.move_selection(1)
            if index > max_index:
                self._ac_loading_more = True
                current_count = max_index + 11
                self._trigger_autocomplete(
                    limit=current_count, initial_index=index
                )
            return "break"
        return ""

    def _on_tab_ac(self, _event: tk.Event) -> str:
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            self.suggestion_popup._confirm_selection()
            return "break"
        return ""

    def _on_escape_ac(self, _event: tk.Event) -> str:
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            self._hide_popup()
            return "break"
        return ""

    def _on_focus_out_ac(self, _event: tk.Event) -> None:
        self.after(150, self._hide_popup)

    def _default_on_right_click(self, index: int, event: tk.Event) -> None:
        self.context_menu_handler.show(index, event)

    def _copy_selection(self) -> None:
        selected_indices = sorted(list(self.model.selected_indices))
        if not selected_indices:
            return
        text = self.separator.join(
            [self.model.tokens[i] for i in selected_indices]
        )
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def _cut_selection(self) -> None:
        self._copy_selection()
        self._delete_selection()

    def _delete_selection(self) -> None:
        self.model.delete_selected()
        self.view.sync_chips()

    def _duplicate_selection(self, index: int) -> None:
        self.model.duplicate_token(index)
        self.view.sync_chips()

    def _insert_placeholder(self, index: int, text: str = "new_token") -> None:
        self.model.insert_token(index, text)
        self.model.clear_selection()
        self.model.select(index)
        self.view.sync_chips()
        self.entry.focus()

    def _reverse_selection(self, indices: List[int]) -> None:
        self.model.reverse_selection()
        self.view.sync_chips()

    def _join_selection(self, indices: List[int]) -> None:
        self.model.join_selection(separator=" ")
        self.view.sync_chips()

    def _group_selection(
        self, indices: List[int], open_char: str, close_char: str
    ) -> None:
        sep = self.separator if self.separator.strip() else " "
        self.model.group_selection(open_char, close_char, separator=sep)
        self.view.sync_chips()

    def _insert_token_after(self, index: int, text: str) -> None:
        self.insert_token(index + 1, text)

    def _replace_with_phrase(self, index: int, phrase: str) -> None:
        self.remove_token(index)
        tokens = self.smart_split(phrase, " ")
        for i, token in enumerate(tokens):
            self.insert_token(index + i, token)

    def _notify_change(self) -> None:
        if self.model.on_change:
            self.model.on_change(self.model.tokens)
