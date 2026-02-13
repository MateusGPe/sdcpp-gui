import time
import tkinter as tk
from enum import Enum, auto
from typing import Callable, List, Optional

from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)

# --- THE STRUCT ---


class ChangeType(Enum):
    INSERT = auto()
    DELETE = auto()
    REPLACE = auto()  # Represents a simultaneous delete + insert


class TextChange:
    """
    Struct for atomic text changes.
    """

    __slots__ = ["type", "index", "text", "original_text", "timestamp"]

    def __init__(
        self, c_type: ChangeType, index: int, text: str, original_text: str = ""
    ):
        self.type = c_type
        self.index = index  # Absolute character index (int)
        self.text = text  # Text added (for insert) or replacement text
        self.original_text = original_text  # Text removed (for delete/replace)
        self.timestamp = time.time()

    def __repr__(self):
        return (
            f"<Change {self.type.name} @ {self.index}: "
            f"'{self.original_text}' -> '{self.text}'>"
        )


class UndoManager:
    def __init__(
        self,
        widget: tk.Text,
        on_change: Optional[Callable] = None,
        max_steps: int = 1000,
        grouping_interval: float = 1.0,
    ):
        """Initializes manager with shadow buffer."""
        self.widget = widget
        self.on_change = on_change
        self.max_steps = max_steps
        self.grouping_interval = grouping_interval

        self._stack: List[TextChange] = []
        self._pointer: int = -1

        self._shadow_text = ""
        self._is_locked = False

        self._update_shadow()
        self.widget.edit_modified(False)
        self.widget.bind("<<Modified>>", self._on_modified, add="+")

    def _update_shadow(self):
        """Syncs shadow text with widget content."""
        self._shadow_text = self.widget.get("1.0", "end-1c")

    def _index_to_int(self, index_str: str) -> int:
        """
        Converts Tkinter index to char offset.
        Returns: int
        """
        try:
            return self.widget.count("1.0", index_str, "chars")[0]
        except (tk.TclError, TypeError):
            return 0

    def _int_to_index(self, char_count: int) -> str:
        """
        Converts char offset to Tkinter index.
        Returns: str
        """
        return f"1.0 + {char_count} chars"

    def _compute_diff(
        self, old_text: str, new_text: str
    ) -> Optional[TextChange]:
        """
        Computes atomic text difference (O(N)).
        Returns: [TextChange | None]
        """
        if old_text == new_text:
            return None

        len_old = len(old_text)
        len_new = len(new_text)
        limit = min(len_old, len_new)

        start = 0
        while start < limit and old_text[start] == new_text[start]:
            start += 1

        end_old = len_old
        end_new = len_new

        while (
            end_old > start
            and end_new > start
            and old_text[end_old - 1] == new_text[end_new - 1]
        ):
            end_old -= 1
            end_new -= 1

        deleted_chunk = old_text[start:end_old]
        inserted_chunk = new_text[start:end_new]

        if deleted_chunk and not inserted_chunk:
            return TextChange(
                ChangeType.DELETE, start, "", original_text=deleted_chunk
            )
        elif inserted_chunk and not deleted_chunk:
            return TextChange(ChangeType.INSERT, start, inserted_chunk)
        else:
            return TextChange(
                ChangeType.REPLACE,
                start,
                inserted_chunk,
                original_text=deleted_chunk,
            )

    def _on_modified(self, event=None):
        """
        Handles text modification.
        Callback: <<Modified>>
        """
        flag = self.widget.edit_modified()
        if not flag:
            return
        self.widget.edit_modified(False)

        if self._is_locked:
            self._update_shadow()
            return

        current_text = self.widget.get("1.0", "end-1c")
        diff = self._compute_diff(self._shadow_text, current_text)

        if diff:
            self._push_change(diff)
            self._shadow_text = current_text

            if self.on_change:
                self.on_change()

    def _push_change(self, change: TextChange):
        """Adds change to stack with coalescing."""
        if self._pointer < len(self._stack) - 1:
            self._stack = self._stack[: self._pointer + 1]

        merged = False
        if self._stack:
            last = self._stack[-1]
            time_diff = change.timestamp - last.timestamp

            if time_diff < self.grouping_interval:
                if (
                    last.type == ChangeType.INSERT
                    and change.type == ChangeType.INSERT
                ):
                    if change.index == last.index + len(last.text):
                        last.text += change.text
                        last.timestamp = change.timestamp
                        merged = True

                elif (
                    last.type == ChangeType.DELETE
                    and change.type == ChangeType.DELETE
                ):
                    if change.index == last.index - len(change.original_text):
                        last.original_text = (
                            change.original_text + last.original_text
                        )
                        last.index = change.index
                        last.timestamp = change.timestamp
                        merged = True
                    elif change.index == last.index:
                        last.original_text += change.original_text
                        last.timestamp = change.timestamp
                        merged = True

        if not merged:
            self._stack.append(change)
            self._pointer += 1

        if len(self._stack) > self.max_steps:
            self._stack.pop(0)
            self._pointer -= 1

    def undo(self):
        """
        Reverts last change.
        Callback: Undo Action
        """
        if self._pointer < 0:
            return

        self._is_locked = True
        try:
            change = self._stack[self._pointer]
            self._pointer -= 1

            start_index = self._int_to_index(change.index)

            if change.type == ChangeType.INSERT:
                end_index = f"{start_index} + {len(change.text)} chars"
                self.widget.delete(start_index, end_index)
                self.widget.mark_set("insert", start_index)

            elif change.type == ChangeType.DELETE:
                self.widget.insert(start_index, change.original_text)
                target_idx = (
                    f"{start_index} + {len(change.original_text)} chars"
                )
                self.widget.mark_set("insert", target_idx)

            elif change.type == ChangeType.REPLACE:
                end_index = f"{start_index} + {len(change.text)} chars"
                self.widget.replace(
                    start_index, end_index, change.original_text
                )
                target_idx = (
                    f"{start_index} + {len(change.original_text)} chars"
                )
                self.widget.mark_set("insert", target_idx)

            self.widget.see("insert")
            self._update_shadow()
            if self.on_change:
                self.on_change()

        finally:
            self._is_locked = False

    def redo(self):
        """
        Reapplies next change.
        Callback: Redo Action
        """
        if self._pointer >= len(self._stack) - 1:
            return

        self._is_locked = True
        try:
            self._pointer += 1
            change = self._stack[self._pointer]

            start_index = self._int_to_index(change.index)

            if change.type == ChangeType.INSERT:
                self.widget.insert(start_index, change.text)
                target_idx = f"{start_index} + {len(change.text)} chars"
                self.widget.mark_set("insert", target_idx)

            elif change.type == ChangeType.DELETE:
                end_index = f"{start_index} + {len(change.original_text)} chars"
                self.widget.delete(start_index, end_index)
                self.widget.mark_set("insert", start_index)

            elif change.type == ChangeType.REPLACE:
                end_index = f"{start_index} + {len(change.original_text)} chars"
                self.widget.replace(start_index, end_index, change.text)
                target_idx = f"{start_index} + {len(change.text)} chars"
                self.widget.mark_set("insert", target_idx)

            self.widget.see("insert")
            self._update_shadow()
            if self.on_change:
                self.on_change()

        finally:
            self._is_locked = False

    def reset(self):
        """Resets history and shadow state."""
        self._stack.clear()
        self._pointer = -1
        self._update_shadow()
