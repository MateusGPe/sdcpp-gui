from __future__ import annotations

import math
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple, Union

from ttkbootstrap.publisher import Channel, Publisher

from sd_cpp_gui.ui.components.color_manager import ColorManager
from sd_cpp_gui.ui.components.nine_slices import NineSliceRenderer

from ..token_chip import TokenChip
from .suggestion_popup import SuggestionPopup

if TYPE_CHECKING:
    pass


class CommandBar(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        suggestion_callback: Callable[
            [List[str]],
            Tuple[
                Union[List[Tuple[str, str]], List[str], type, Tuple, None], str
            ],
        ],
        on_command: Optional[Callable[[List[str]], None]] = None,
        on_search_change: Optional[Callable[[str], None]] = None,
        bootstyle: str = "",
        height: int = 48,
        bg_color: Optional[str] = None,
        border_color: Optional[str] = None,
        focus_color: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Logic: Initializes command bar, popup, chips frame, entry,
        and binds events."""
        super().__init__(
            parent, height=height, highlightthickness=0, bd=0, **kwargs
        )
        self.tokens: List[str] = []
        self.suggestion_callback = suggestion_callback
        self.on_command_callback = on_command
        self.on_search_change = on_search_change
        self.placeholder_text = "Type / to command, or just type to search..."
        self._input_locked = False
        self._current_validator: Any = None
        self._shake_offset = 0
        overrides = {
            "bg": bg_color,
            "border": border_color,
            "focus": focus_color,
        }
        self.color_manager = ColorManager(
            parent, overrides=overrides, bootstyle=bootstyle
        )
        self.popup = SuggestionPopup(
            self.winfo_toplevel(),
            self._on_suggestion_selected,
            self.color_manager,
        )
        self.radius = 8
        self.border_width = 1
        self.elevation = 1
        self._draw_job = None
        self.safe_pad = (
            math.ceil(self.radius * (1 - math.sqrt(2) / 2))
            + 3
            + self.border_width * 2
        )
        self.ns_renderer = NineSliceRenderer(
            radius=self.radius,
            border_width=self.border_width,
            elevation=self.elevation,
        )
        self.chip_renderer = NineSliceRenderer(
            radius=8, border_width=0, elevation=0
        )
        self.container = tk.Frame(self, bd=0, highlightthickness=0)
        self._window_id = self.create_window(
            0, 0, window=self.container, anchor="center"
        )
        self.chip_frame = tk.Frame(self.container, bd=0, highlightthickness=0)
        self.entry = tk.Entry(
            self.container,
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self.entry.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(self.safe_pad, self.safe_pad),
            pady=6,
        )
        self.lbl_placeholder = tk.Label(
            self.container,
            text=self.placeholder_text,
            font=("Segoe UI", 9, "italic"),
            anchor="w",
            bd=0,
            highlightthickness=0,
        )
        self.lbl_icon = tk.Label(
            self.container,
            text="🔍",
            font=("Segoe UI Emoji", 9),
            anchor="center",
            bd=0,
            highlightthickness=0,
        )
        self.lbl_icon.pack(side="right")
        self.bind("<Configure>", self._on_resize)
        for w in (
            self,
            self.container,
            self.chip_frame,
            self.lbl_placeholder,
            self.lbl_icon,
        ):
            w.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Return>", self._on_enter_pressed)
        self.entry.bind("<Tab>", self._on_tab_pressed)
        self.entry.bind("<BackSpace>", self._on_backspace)
        self.entry.bind("<Up>", self._on_arrow_up)
        self.entry.bind("<Down>", self._on_arrow_down)
        self.entry.bind("<Escape>", lambda e: self.popup.hide())
        self.bind("<Destroy>", self._on_destroy)
        Publisher.subscribe(
            name=str(id(self)), func=self.on_theme_change, channel=Channel.STD
        )
        self.update_appearance()
        self._update_placeholder_visibility()

    def clear(self) -> None:
        """Logic: Clears tokens and entry text."""
        self.tokens.clear()
        if self.entry.winfo_exists():
            self.entry.delete(0, tk.END)
        self.popup.hide()
        self._rebuild_chips()
        self._refresh_context()
        self._update_icon()

    def set_tokens(self, tokens: List[str]) -> None:
        """Logic: Sets tokens and refreshes UI."""
        self.tokens = list(tokens)
        if self.entry.winfo_exists():
            self.entry.delete(0, tk.END)
        self.popup.hide()
        self._rebuild_chips()
        self._refresh_context()
        self._update_icon()

    def get_value(self) -> dict:
        """Logic: Returns current tokens and text."""
        text = self.entry.get() if self.entry.winfo_exists() else ""
        return {"tokens": self.tokens, "text": text}

    def on_theme_change(self, _note: Optional[Any] = None) -> None:
        """Logic: Updates appearance on theme change."""
        if not self.winfo_exists():
            Publisher.unsubscribe(str(id(self)))
            return
        self.update_appearance()

    def update_appearance(self) -> None:
        """Logic: Updates colors for all components."""
        if not self.winfo_exists():
            return
        palette = self.color_manager.update_palette()
        bg_parent = palette["parent"]
        bg_entry = palette["bg"]
        fg_text = self.color_manager.ensure_contrast(bg_entry, "#222222")
        fg_placeholder = self.color_manager._mix_colors(fg_text, bg_entry, 0.5)
        self.configure(bg=bg_parent)
        self.container.configure(bg=bg_entry)
        self.chip_frame.configure(bg=bg_entry)
        is_valid = True
        if self._current_validator and self.entry.get():
            is_valid = self._validate_input(
                self.entry.get(), self._current_validator
            )
        final_fg = fg_text if is_valid else "#e74c3c"
        self.entry.configure(
            bg=bg_entry,
            fg=final_fg,
            insertbackground=fg_text,
            highlightthickness=0,
            bd=0,
        )
        self.lbl_placeholder.configure(bg=bg_entry, fg=fg_placeholder)
        self.lbl_icon.configure(bg=bg_entry, fg=fg_placeholder)
        sep_col = self.color_manager._mix_colors(
            bg_entry, palette["border"], 0.5
        )
        for child in self.chip_frame.winfo_children():
            if isinstance(child, TokenChip):
                child.update_colors()
            elif isinstance(child, tk.Canvas) and "separator" in child.gettags(
                "sep"
            ):
                child.delete("all")
                w, h = (child.winfo_width(), child.winfo_height())
                child.create_text(
                    w / 2,
                    h / 2,
                    text="›",
                    fill=sep_col,
                    font=("Arial", 12),
                    tags=("sep", "separator"),
                )
                child.configure(bg=bg_entry)
        self.ns_renderer.generate_slices(palette)
        self._schedule_redraw()

    def _schedule_redraw(self) -> None:
        """Logic: Debounces redraw."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
        self._draw_job = self.after(10, self._redraw_canvas)

    def _redraw_canvas(self) -> None:
        """Logic: Draws the background."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
            self._draw_job = None
        if not self.winfo_exists():
            return
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 1 and h > 1:
            self.ns_renderer.draw_on_canvas(self, w, h)
            inner_w = max(1, w - self.safe_pad * 2)
            inner_h = max(1, h - self.safe_pad * 2)
            self.itemconfigure(self._window_id, width=inner_w, height=inner_h)
            self.coords(self._window_id, w / 2 + self._shake_offset, h / 2)
            self.tag_raise(self._window_id)

    def _on_resize(self, _event: tk.Event) -> None:
        """Logic: Triggers redraw on resize."""
        self._schedule_redraw()

    def _on_focus_in(self, _event: tk.Event) -> None:
        """Logic: Sets focus state and checks input."""
        self.color_manager.set_focus_state(True)
        self.update_appearance()
        if not self._input_locked and self.entry.get():
            self._handle_input_change()

    def _on_focus_out(self, _event: tk.Event) -> None:
        """Logic: Unsets focus state and hides popup."""
        self.color_manager.set_focus_state(False)
        self.update_appearance()
        self.after(150, self.popup.hide)
        self._deselect_last_token()

    def _on_key_release(self, event: tk.Event) -> None:
        """Logic: Handles input changes, validation, and suggestions."""
        if event.keysym in (
            "Up",
            "Down",
            "Return",
            "BackSpace",
            "Escape",
            "Tab",
        ):
            return
        if self._current_validator and (not self._input_locked):
            text = self.entry.get()
            if text and (
                not self._validate_input(text, self._current_validator)
            ):
                self.entry.config(fg="#e74c3c")
            else:
                self.entry.config(
                    fg=self.color_manager.ensure_contrast(
                        self.color_manager.palette["bg"], "#222222"
                    )
                )
        if not self._input_locked:
            self._handle_input_change()
        self._update_placeholder_visibility()
        self._update_icon()

    def _validate_input(self, text: str, rule: Any) -> bool:
        """Logic: Validates input against rule (type, list, range)."""
        try:
            if rule is int:
                if text in ("", "-", "+"):
                    return True
                int(text)
                return True
            if rule is float:
                if text in ("", "-", "+", ".", "-."):
                    return True
                float(text)
                return True
            if isinstance(rule, list):
                return text in rule
            if isinstance(rule, tuple) and len(rule) >= 1:
                val = rule[0](text)
                if len(rule) >= 3:
                    return rule[1] <= val <= rule[2]
                return True
        except ValueError:
            return False
        return True

    def _handle_input_change(self) -> None:
        """Decides whether to trigger command suggestions or search filter.

        Logic: Triggers suggestions if command mode, else triggers search."""
        text = self.entry.get()
        if self.tokens or text.startswith("/") or text.startswith("-"):
            self._trigger_suggestions()
        else:
            self.popup.hide()
            if self.on_search_change:
                self.on_search_change(text)

    def _trigger_suggestions(self) -> None:
        """Logic: Fetches suggestions and shows popup if matches found."""
        query = self.entry.get()
        possible, _ = self.suggestion_callback(self.tokens)
        if isinstance(possible, list):
            if possible and isinstance(possible[0], (tuple, list)):
                matches = [
                    item
                    for item in possible
                    if query.lower() in item[0].lower()
                    or query.lower() in item[1].lower()
                ]
            else:
                matches = [s for s in possible if query.lower() in s.lower()]
            if matches:
                x, y = (self.winfo_rootx(), self.winfo_rooty())
                self.popup.show(x, y, self.winfo_width(), matches)
            else:
                self.popup.hide()
        else:
            self.popup.hide()

    def _on_suggestion_selected(self, text: str) -> None:
        """Logic: Adds selected suggestion as token."""
        self.add_token(text)
        self.entry.focus_set()

    def _on_enter_pressed(self, _event: tk.Event) -> str:
        """Logic: Confirms suggestion, adds token, or submits command/search."""
        if self.popup.state() == "normal":
            sel = self.popup.get_current_selection()
            if sel:
                self.add_token(sel)
                return "break"
        text = self.entry.get().strip()
        if (
            not self.tokens
            and (not text.startswith("/"))
            and (not text.startswith("-"))
        ):
            if self.on_search_change:
                self.on_search_change(text)
            return "break"
        if text:
            if self._current_validator and (
                not self._validate_input(text, self._current_validator)
            ):
                self._shake_animate()
                return "break"
            self.add_token(text)
            return "break"
        if self.tokens:
            if self.on_command_callback:
                self.on_command_callback(self.tokens)
        return "break"

    def _shake_animate(self, step: int = 0) -> None:
        """Logic: Animates shake effect on invalid input."""
        if not self.winfo_exists():
            return
        offsets = [0, -4, 4, -4, 4, -2, 2, 0]
        if step < len(offsets):
            self._shake_offset = offsets[step]
            self._redraw_canvas()
            self.after(60, lambda: self._shake_animate(step + 1))
        else:
            self._shake_offset = 0
            self._redraw_canvas()

    def _on_tab_pressed(self, _event: tk.Event) -> Optional[str]:
        """Logic: Auto-completes suggestion."""
        if self.popup.state() == "normal":
            sel = self.popup.get_current_selection()
            if sel:
                self.add_token(sel)
                return "break"
        return None

    def _on_arrow_down(self, _e: tk.Event) -> str:
        """Logic: Navigates suggestions down."""
        if self.popup.state() == "normal":
            self.popup.move_selection(1)
        else:
            self._trigger_suggestions()
        return "break"

    def _on_arrow_up(self, _e: tk.Event) -> str:
        """Logic: Navigates suggestions up."""
        if self.popup.state() == "normal":
            self.popup.move_selection(-1)
        return "break"

    def _on_backspace(self, _event: tk.Event) -> Optional[str]:
        """Logic: Removes last token if input is empty."""
        if not self.winfo_exists():
            return None
        if self._input_locked:
            self._set_input_locked(False)
            return "break"
        if self.entry.get():
            if not self.tokens:
                self.after(1, self._handle_input_change)
            return None
        if not self.tokens:
            return None
        if not self.chip_frame.winfo_exists():
            return None
        children = [
            c
            for c in self.chip_frame.winfo_children()
            if isinstance(c, TokenChip)
        ]
        if not children:
            return None
        last_widget = children[-1]
        if last_widget._is_selected:
            self.tokens.pop()
            self._rebuild_chips()
            self.event_generate("<<TokenRemoved>>")
        else:
            self._deselect_last_token()
            last_widget.set_selected(True)
        return "break"

    def add_token(self, text: str) -> None:
        """Logic: Adds a new token chip."""
        self.tokens.append(text)
        self.entry.delete(0, tk.END)
        self.popup.hide()
        self._rebuild_chips()
        self._update_icon()
        self.event_generate("<<TokenAdded>>")

    def remove_token_at(self, index: int) -> None:
        """Logic: Removes token at index."""
        if 0 <= index < len(self.tokens):
            self.tokens.pop(index)
            self._rebuild_chips()
            self._update_icon()
            self.event_generate("<<TokenRemoved>>")

    def _deselect_last_token(self) -> None:
        """Logic: Deselects the last token chip."""
        if not self.chip_frame.winfo_exists():
            return
        for w in self.chip_frame.winfo_children():
            if isinstance(w, TokenChip):
                w.set_selected(False)

    def _rebuild_chips(self) -> None:
        """Logic: Recreates all token chips."""
        if not self.chip_frame.winfo_exists():
            return
        for w in self.chip_frame.winfo_children():
            try:
                if w.winfo_exists():
                    w.destroy()
            except tk.TclError:
                pass
        if not self.tokens:
            self.chip_frame.pack_forget()
            self.entry.pack_configure(padx=(self.safe_pad, self.safe_pad))
        else:
            palette = self.color_manager.palette
            sep_col = self.color_manager._mix_colors(
                palette["bg"], palette["border"], 0.5
            )
            bg_col = palette["bg"]
            for i, text in enumerate(self.tokens):
                is_command = text.startswith("/") or text.startswith("-")
                variant = "default" if is_command else "leaf"
                chip = TokenChip(
                    self.chip_frame,
                    text,
                    lambda idx=i: self.remove_token_at(idx),
                    self.color_manager,
                    self.entry.focus_set,
                    self.chip_renderer,
                    variant=variant,
                )
                chip.pack(side="left", padx=(0, 2), pady=2)
                cv = tk.Canvas(
                    self.chip_frame,
                    width=12,
                    height=24,
                    bg=bg_col,
                    bd=0,
                    highlightthickness=0,
                )
                cv.pack(side="left")
                cv.create_text(
                    6,
                    12,
                    text="›",
                    fill=sep_col,
                    font=("Arial", 12),
                    tags=("sep", "separator"),
                )
            self.chip_frame.pack(
                side="left",
                fill="y",
                padx=(self.safe_pad, 0),
                before=self.entry,
            )
            self.entry.pack_configure(padx=(4, self.safe_pad))
        self._refresh_context()

    def _refresh_context(self) -> None:
        """
        Logic: Updates placeholder and input locking based on
        current context."""
        result, placeholder = self.suggestion_callback(self.tokens)
        self.placeholder_text = placeholder
        self._current_validator = None
        if result is None:
            self._set_input_locked(True)
        elif isinstance(result, list):
            self._set_input_locked(False)
        else:
            self._current_validator = result
            self._set_input_locked(False)
        self._update_placeholder_visibility()

    def _set_input_locked(self, locked: bool) -> None:
        """Toggles the 'Ready to Run' state.

        Logic: Hides entry and shows 'Press Enter' label if locked."""
        self._input_locked = locked
        if locked:
            self.entry.pack_forget()
            self.lbl_placeholder.config(
                text="Press Enter to Run",
                fg=str(self.color_manager.palette.get("focus", "#007acc")),
            )
            self.lbl_placeholder.place(relx=0, rely=0, relheight=1, relwidth=1)
            self.lbl_placeholder.lift()
        else:
            if not self.entry.winfo_ismapped():
                self.entry.pack(
                    side="left",
                    fill="both",
                    expand=True,
                    padx=(4, self.safe_pad),
                )
                self.entry.focus_set()
            self._update_placeholder_visibility()

    def _update_placeholder_visibility(self) -> None:
        """Logic: Shows/hides placeholder text."""
        if self._input_locked:
            return
        if not self.entry.get():
            self.lbl_placeholder.config(
                text=self.placeholder_text, fg="#999999"
            )
            self.lbl_placeholder.place(
                in_=self.entry, relx=0, rely=0, relheight=1, relwidth=1
            )
            self.lbl_placeholder.lift()
        else:
            self.lbl_placeholder.place_forget()

    def _update_icon(self) -> None:
        """Changes the icon based on context (Command vs Search).

        Logic: Updates status icon."""
        if (
            self.tokens
            or self.entry.get().startswith("/")
            or self.entry.get().startswith("-")
        ):
            self.lbl_icon.configure(text="❯_")
        else:
            self.lbl_icon.configure(text="🔍")

    def _on_destroy(self, _event: tk.Event) -> None:
        """Logic: Clean up."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
        Publisher.unsubscribe(str(id(self)))
