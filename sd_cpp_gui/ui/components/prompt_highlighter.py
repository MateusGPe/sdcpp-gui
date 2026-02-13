import re
import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import ttkbootstrap as tb
from ttkbootstrap.publisher import Publisher

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.ui.components.command_bar.suggestion_popup import (
    SuggestionPopup,
)

from .text import MText
from .undo_manager import UndoManager

if TYPE_CHECKING:
    from sd_cpp_gui.domain.services.autocomplete_service import (
        AutocompleteService,
    )


SHIFT = 1
CONTROL = 4


class PromptHighlighter(MText):
    def __init__(
        self,
        master,
        flag=None,
        name=None,
        autocomplete_service: Optional["AutocompleteService"] = None,
        **kwargs,
    ):
        """
        Initializes prompt editor with syntax highlighting and
        delta-compressed undo stack.
        """
        if not (var := kwargs.pop("textvariable", None)):
            var = tk.StringVar()
        self.var_value = var
        self.flag = flag
        self.name = name or "Prompt"
        self.var_enabled = tk.BooleanVar(value=False)

        self.autocomplete_service = autocomplete_service
        self.suggestion_popup: Optional[SuggestionPopup] = None

        self._ac_disabled = False
        self._ac_job = None
        self._ac_loading_more = False
        self._highlight_job = None
        self._syncing = False

        self._re_lora = re.compile(r"<lora:[^:]+:[+-]?\d+\.?\d*>")
        self._re_weight_num = re.compile(r"(?<=:)[+-]?\d+\.?\d*")

        # Disable native undo to use custom Delta-Compressed UndoManager
        kwargs["undo"] = False
        kwargs["autoseparators"] = False
        super().__init__(master, **kwargs)

        self.update_tag_colors()

        # Custom Undo Manager (Delta-Compressed & Coalescing)
        # on_change ensures highlighting updates during undo/redo operations
        self.undo_manager = UndoManager(
            self,
            on_change=self._schedule_highlight,
            max_steps=1000,
            grouping_interval=0.6,
        )

        # Highlighting Bindings
        self.bind("<KeyRelease>", self._schedule_highlight, add="+")
        self.bind("<<Paste>>", self._on_paste)
        self.bind("<<Cut>>", self._schedule_highlight, add="+")

        # Numeric Weight Adjustment Bindings
        self.bind("<Prior>", self._on_arrow_key, add="+")
        self.bind("<Next>", self._on_arrow_key, add="+")

        # Undo/Redo Bindings
        self.bind("<Control-z>", self._on_undo)
        self.bind("<Control-y>", self._on_redo)
        self.bind("<Control-Z>", self._on_redo)  # Shift+Ctrl+Z support
        self.bind("<<Undo>>", self._on_undo)
        self.bind("<<Redo>>", self._on_redo)

        if self.autocomplete_service:
            self.bind("<KeyRelease>", self._on_key_release_ac, add="+")
            self.bind("<Up>", self._on_up_ac, add="+")
            self.bind("<Down>", self._on_down_ac, add="+")
            self.bind("<Tab>", self._on_tab_ac, add="+")
            self.bind("<Return>", self._on_enter_ac, add="+")
            self.bind("<Escape>", self._on_escape_ac, add="+")
            self.bind("<FocusOut>", self._on_focus_out_ac, add="+")

        self.var_value.trace_add("write", self._on_var_change)
        self.highlight()

    def _on_undo(self, event=None):
        """
        Triggers custom undo operation.
        Callback: <Control-z> / <<Undo>>
        """
        self.undo_manager.undo()
        return "break"

    def _on_redo(self, event=None):
        """
        Triggers custom redo operation.
        Callback: <Control-y> / <<Redo>>
        """
        self.undo_manager.redo()
        return "break"

    def on_theme_change(self, note=None):
        """
        Reconfigures highlight colors and refreshes tags.
        Listens: Theme Changed
        """
        if not self.winfo_exists():
            Publisher.unsubscribe(str(id(self)))
            return
        super().on_theme_change(note)
        self.update_tag_colors()
        self.highlight()
        if self.suggestion_popup:
            self.suggestion_popup.hide()
            self.suggestion_popup = None

    def _on_var_change(self, *_):
        """
        Syncs widget text with bound variable. Resets undo history
        on external load.
        Callback: textvariable write
        """
        if self._syncing:
            return
        new_text = self.var_value.get()
        current_text = self.get("1.0", "end-1c")

        # Check actual difference to avoid loops
        if current_text != new_text:
            self._syncing = True

            # Atomic replace triggers UndoManager's <<Modified>> listener.
            # However, external loads (presets) usually shouldn't be undoable
            # via the stack relative to the previous state.
            self.replace("1.0", "end", new_text)
            self.undo_manager.reset()

            self.highlight(update_var=False)
            self._syncing = False

    @property
    def arg_type(self) -> str:
        """
        Returns argument type identifier.
        Returns: 'string'
        """
        return "string"

    @property
    def is_overridden(self) -> bool:
        """
        Checks if control is overridden.
        Returns: bool
        """
        return False

    def set_override_mode(self, active: bool):
        """
        Sets override mode (No-op).
        """
        pass

    def replace(self, index1, index2, chars, *args):
        """
        Overrides base replace to schedule visual refresh.
        """
        super().replace(index1, index2, chars, *args)
        self._schedule_highlight(delay=10)

    def insert(self, index, chars, *args):
        """
        Overrides base insert to schedule visual refresh.
        """
        super().insert(index, chars, *args)
        self._schedule_highlight(delay=10)

    def delete(self, index1, index2=None):
        """
        Overrides base delete to schedule visual refresh.
        """
        super().delete(index1, index2)
        self._schedule_highlight()

    def _on_destroy(self, event=None):
        """
        Cleans up jobs and popup resources.
        Callback: <Destroy>
        """
        if self._highlight_job:
            try:
                self.after_cancel(self._highlight_job)
            except tk.TclError:
                pass
        if self.suggestion_popup:
            self.suggestion_popup.destroy()
        super()._on_destroy(event)

    def _on_paste(self, event=None):
        """
        Handles paste via atomic replace to support custom undo.
        Callback: <<Paste>>
        """
        try:
            text = self.clipboard_get()
            try:
                sel_start = self.index("sel.first")
                sel_end = self.index("sel.last")
                self.replace(sel_start, sel_end, text)
            except tk.TclError:
                self.insert("insert", text)
            self.see("insert")
            return "break"
        except Exception:
            return "break"

    def update_tag_colors(self) -> None:
        """
        Configures syntax highlighting colors based on active theme,
        ensuring contrast against the background.
        """
        bg_color = self.color_manager.palette.get("bg", "#ffffff")

        try:
            style = tb.Style.get_instance()
            colors = style.colors
            raw_inc = colors.info
            raw_dec = colors.danger
            raw_lora = colors.warning
            raw_weight = colors.success
        except Exception:
            raw_inc = "#4ec9b0"
            raw_dec = "#c586c0"
            raw_lora = "#ce9178"
            raw_weight = "#dcdcaa"

        color_inc = self.color_manager.ensure_contrast(bg_color, raw_inc)
        color_dec = self.color_manager.ensure_contrast(bg_color, raw_dec)
        color_lora = self.color_manager.ensure_contrast(bg_color, raw_lora)
        color_weight = self.color_manager.ensure_contrast(bg_color, raw_weight)

        self.tag_configure("attention_inc", foreground=color_inc)
        self.tag_configure("attention_dec", foreground=color_dec)
        self.tag_configure("lora_tag", foreground=color_lora)
        self.tag_configure(
            "weight_num",
            foreground=color_weight,
            font=(SYSTEM_FONT, 10, "bold"),
        )

    def save_view_state(self) -> Tuple[str, Tuple[float, float]]:
        """
        Captures cursor index and scroll position.
        Returns: (index, yview)
        """
        try:
            return (self.index(tk.INSERT), self.yview())
        except tk.TclError:
            return ("1.0", (0.0, 1.0))

    def restore_view_state(
        self, state: Tuple[str, Tuple[float, float]]
    ) -> None:
        """
        Restores cursor index and scroll position.
        """
        index, yview = state
        try:
            self.mark_set(tk.INSERT, index)
            self.see(tk.INSERT)
            self.yview_moveto(yview[0])
        except tk.TclError:
            pass

    def highlight(self, update_var=True):
        """
        Parses text and applies syntax tags (LoRA, weights, parens).
        """
        view_state = self.save_view_state()
        content = self.get("1.0", "end-1c")

        if update_var and (not self._syncing):
            self._syncing = True
            if self.var_value.get() != content:
                self.var_value.set(content)
            has_text = bool(content.strip())
            if self.var_enabled.get() != has_text:
                self.var_enabled.set(has_text)
            self._syncing = False

        matches = {
            "lora_tag": [],
            "attention_inc": [],
            "attention_dec": [],
            "weight_num": [],
        }

        for match in self._re_lora.finditer(content):
            matches["lora_tag"].append((match.start(), match.end()))

        paren_matches = self._find_balanced_delimiters(content, "(", ")")
        matches["attention_inc"].extend(paren_matches)

        bracket_matches = self._find_balanced_delimiters(content, "[", "]")
        matches["attention_dec"].extend(bracket_matches)

        for match in self._re_weight_num.finditer(content):
            matches["weight_num"].append((match.start(), match.end()))

        for tag, ranges in matches.items():
            self._update_tag(tag, ranges)

        self.restore_view_state(view_state)

    def _update_tag(self, tag: str, ranges: List[Tuple[int, int]]):
        """
        Updates a specific tag only if the ranges have changed.
        """
        if not ranges:
            merged_ranges = []
        else:
            ranges.sort(key=lambda x: x[0])
            merged_ranges = []
            curr_start, curr_end = ranges[0]
            for i in range(1, len(ranges)):
                next_start, next_end = ranges[i]
                if next_start <= curr_end:
                    curr_end = max(curr_end, next_end)
                else:
                    merged_ranges.append((curr_start, curr_end))
                    curr_start, curr_end = next_start, next_end
            merged_ranges.append((curr_start, curr_end))

        new_ranges_flat = []
        for start, end in merged_ranges:
            s = self.index(f"1.0 + {start} chars")
            e = self.index(f"1.0 + {end} chars")
            new_ranges_flat.extend([s, e])

        curr_ranges_flat = self.tag_ranges(tag)
        if tuple(new_ranges_flat) == curr_ranges_flat:
            return

        self.tag_remove(tag, "1.0", "end")
        if new_ranges_flat:
            self.tag_add(tag, *new_ranges_flat)

    def _schedule_highlight(self, _event=None, delay=300):
        """
        Debounces highlight execution.
        """
        if self._highlight_job:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(delay, self.highlight)

    def _on_arrow_key(self, event: tk.Event):
        """
        Increments/decrements numerical weight under cursor.
        Callback: <Prior> (PageUp) / <Next> (PageDown)
        """
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            return None

        step = 0.1
        if event.state & SHIFT:
            step = 0.01
        elif event.state & CONTROL:
            step = 1.0

        try:
            insert_index = self.index(tk.INSERT)
            line_idx = int(insert_index.split(".")[0])
            col_idx = int(insert_index.split(".")[1])
            line_text = self.get(f"{line_idx}.0", f"{line_idx}.end")
        except tk.TclError:
            return None

        number_regex = re.compile(r"(?<=:)(?:[-+]?\d*\.\d+|[-+]?\d+)")
        target_match = None

        for match in number_regex.finditer(line_text):
            start, end = match.span()

            # Check if part of a word (preceded or followed
            # by letter/underscore)
            if start > 0:
                prev_char = line_text[start - 1]
                if prev_char.isalpha() or prev_char == "_":
                    continue
            if end < len(line_text):
                next_char = line_text[end]
                if next_char.isalpha() or next_char == "_":
                    continue

            if end >= col_idx:
                target_match = match
                break

        if target_match:
            start, end = target_match.span()
            try:
                current_value = float(target_match.group(0))
            except ValueError:
                return None

            new_value = (
                current_value + step
                if event.keysym == "Prior"
                else current_value - step
            )

            if step == 0.01:
                new_value = round(new_value, 2)
            elif step == 0.1:
                new_value = round(new_value, 1)
            else:
                new_value = round(new_value)

            new_value_str = str(new_value)
            start_index = f"{line_idx}.{start}"
            end_index = f"{line_idx}.{end}"

            # Atomic replace ensures clean undo history
            self.replace(start_index, end_index, new_value_str)

            new_end_offset = start + len(new_value_str)
            self.mark_set(tk.INSERT, f"{line_idx}.{new_end_offset}")
            self.see(tk.INSERT)
            return "break"
        return None

    def _find_balanced_delimiters(
        self, text: str, open_delim: str, close_delim: str
    ) -> list[tuple[int, int]]:
        """
        Returns list of (start, end) indices for matching delimiters.
        Returns: [(start, end), ...]
        """
        stack = []
        matches = []
        for i, char in enumerate(text):
            if char == open_delim:
                stack.append(i)
            elif char == close_delim:
                if stack:
                    start = stack.pop()
                    matches.append((start, i + 1))
        return matches

    def toggle_state(self):
        """
        Toggles enabled state (No-op for highlighter).
        """
        return

    def get_status(self) -> Dict[str, Any]:
        """
        Returns control status metadata.
        Returns: Dict {enabled, value, name, ...}
        """
        return {
            "enabled": self.var_enabled.get(),
            "value": self.var_value.get(),
            "name": self.name,
            "flag": self.flag,
            "arg_type": "string",
            "description": "",
            "default_val": "",
            "is_required": False,
            "file_types": None,
            "open_mode": None,
            "options": None,
        }

    def _on_key_release_ac(self, event):
        """
        Debounces autocomplete trigger.
        Callback: <KeyRelease>
        """
        if (
            event.keysym
            in (
                "Up",
                "Down",
                "Return",
                "Tab",
                "Escape",
                "Prior",
                "Next",
                "Shift_L",
                "Shift_R",
                "Control_L",
                "Control_R",
                "Alt_L",
                "Alt_R",
            )
            or self._ac_disabled
        ):
            return

        if self._ac_job:
            self.after_cancel(self._ac_job)

        self._ac_job = self.after(100, self._trigger_autocomplete)

    def _trigger_autocomplete(self, limit: int = 10, initial_index: int = 0):
        """
        Searches autocomplete service and displays suggestions.
        """
        try:
            if self._ac_job:
                self.after_cancel(self._ac_job)
                self._ac_job = None

            if not self.autocomplete_service:
                return

            try:
                line_start = self.index("insert linestart")
                cursor = self.index("insert")
                text = self.get(line_start, cursor)
            except tk.TclError:
                return

            if not text.strip() or len(text) < 2:
                self._hide_popup()
                return

            results = self.autocomplete_service.search(text, limit=limit)

            if not results:
                self._hide_popup()
                return

            if initial_index > 0 and len(results) <= initial_index:
                initial_index = len(results) - 1

            popup_items = [(r[0], r[4]) for r in results]

            # Calculate popup position based on current word
            query = text.lower().lstrip()
            parts = re.split(r"[\s<>()\{\}\[\],\.\|:]", query)
            word_len = len(parts[-1])
            start_index = f"insert-{word_len}c"

            self._show_popup(
                popup_items,
                start_index=start_index,
                initial_index=initial_index,
            )
        finally:
            self._ac_loading_more = False

    def _show_popup(
        self,
        items: List[Tuple[str, str]],
        start_index: str = "insert",
        initial_index: int = 0,
    ):
        """
        Displays suggestion popup at cursor coordinates.
        """
        if not self.suggestion_popup:
            self.suggestion_popup = SuggestionPopup(
                self, self._on_suggestion_selected, self.color_manager
            )

        self.update_idletasks()

        bbox = self.bbox(start_index)

        if not bbox:
            bbox = self.bbox("insert")

        if not bbox:
            return

        x, y, _, h = bbox

        root_x = self.winfo_rootx() + x
        root_y = self.winfo_rooty() + y + h

        self.suggestion_popup.show(
            root_x,
            root_y,
            300,
            items,
            autolayout=False,
            initial_index=initial_index,
        )

    def _hide_popup(self):
        """
        Hides suggestion popup.
        """
        if self.suggestion_popup:
            self.suggestion_popup.hide()

    def _on_suggestion_selected(self, raw_name: str):
        """
        Replaces typed fragment with selected suggestion.
        Callback: SuggestionPopup Select
        """
        try:
            line_start = self.index("insert linestart")
            cursor = self.index("insert")
            line_text = self.get(line_start, cursor)

            raw_name = re.sub(r"([\(\)\[\]:])", r"\\\1", raw_name)
            parts = re.split(r"[\s<>()\{\}\[\],\.\|:]", line_text)
            fragment = parts[-1]

            # Use atomic replace for clean undo history
            if not fragment:
                self.insert("insert", raw_name)
            else:
                delete_start = f"insert -{len(fragment)}c"
                self.replace(delete_start, "insert", raw_name)

            self._hide_popup()
            self.highlight()

        except tk.TclError:
            pass

    def _on_up_ac(self, event):
        """
        Navigates suggestion selection up.
        Callback: <Up>
        """
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            self.suggestion_popup.move_selection(-1)
            return "break"

    def _on_down_ac(self, event):
        """
        Navigates suggestion selection down or loads more results.
        Callback: <Down>
        """
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

        self._ac_disabled = False
        self._trigger_autocomplete()
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            return "break"
        return None

    def _on_tab_ac(self, event):
        """
        Confirms suggestion selection.
        Callback: <Tab>
        """
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            self.suggestion_popup._confirm_selection()
            return "break"

    def _on_enter_ac(self, event):
        """
        Confirms suggestion selection.
        Callback: <Return>
        """
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            self.suggestion_popup._confirm_selection()
            return "break"

    def _on_escape_ac(self, event):
        """
        Closes suggestion popup.
        Callback: <Escape>
        """
        if self.suggestion_popup and self.suggestion_popup.winfo_ismapped():
            self._hide_popup()
            self._ac_disabled = True
            return "break"

    def _on_focus_out_ac(self, event):
        """
        Hides popup on focus loss.
        Callback: <FocusOut>
        """
        self.after(150, self._hide_popup)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("SD Prompt Editor")
    root.configure(bg="#1e1e1e")
    editor = PromptHighlighter(
        root,
        bg_color="#1e1e1e",
        fg_color="#d4d4d4",
        insertbackground="white",
        selectbackground="#264f78",
        font=("Consolas", 11),
    )
    editor.pack(expand=True, fill="both", padx=10, pady=10)
    sample = (
        "masterprice high quality abstract portrait"
        " <lora:Detail Slider V2 By Stable :1.47> (high quality:1.3), [blurry]"
    )
    editor.insert("1.0", sample)
    editor.highlight()
    root.mainloop()
