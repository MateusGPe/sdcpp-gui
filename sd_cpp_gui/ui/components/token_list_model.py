from __future__ import annotations

from typing import Callable, List, Optional, Set


class TokenListModel:
    """
    Manages the data state of the token list: tokens, selection, and history.
    """

    def __init__(
        self,
        on_change: Optional[Callable[[List[str]], None]] = None,
        on_selection_change: Optional[
            Callable[[Optional[int], str], None]
        ] = None,
    ):
        self._tokens: List[str] = []
        self._selected_indices: Set[int] = set()
        self._anchor_index: Optional[int] = None
        self.on_change = on_change
        self.on_selection_change = on_selection_change

    @property
    def tokens(self) -> List[str]:
        return list(self._tokens)

    @property
    def selected_indices(self) -> Set[int]:
        return set(self._selected_indices)

    def set_tokens(self, tokens: List[str]) -> bool:
        new_tokens = [t.strip() for t in tokens if t.strip()]
        if new_tokens == self._tokens:
            return False
        self._tokens = new_tokens
        self.clear_selection()
        return True

    def get_tokens(self) -> List[str]:
        return list(self._tokens)

    def add_tokens(self, new_tokens: List[str]) -> None:
        self._tokens.extend(new_tokens)
        self._notify_change()

    def insert_token(self, index: int, text: str) -> None:
        self._tokens.insert(index, text)
        self._notify_change()

    def update_token(self, index: int, text: str) -> None:
        if 0 <= index < len(self._tokens):
            self._tokens[index] = text
            self._notify_change()

    def remove_token(self, index: int) -> None:
        if 0 <= index < len(self._tokens):
            self._tokens.pop(index)
            self._adjust_selection_after_removal(index)
            self._notify_change()

    def move_token(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return

        self._tokens[from_index], self._tokens[to_index] = (
            self._tokens[to_index],
            self._tokens[from_index],
        )

        new_indices = set()
        for i in self._selected_indices:
            if i == from_index:
                new_indices.add(to_index)
            elif i == to_index:
                new_indices.add(from_index)
            else:
                new_indices.add(i)
        self._selected_indices = new_indices

        if self._anchor_index == from_index:
            self._anchor_index = to_index
        elif self._anchor_index == to_index:
            self._anchor_index = from_index

        self._notify_change()
        self._notify_selection()

    def select(
        self, index: int, multi: bool = False, range_select: bool = False
    ) -> None:
        if range_select and self._anchor_index is not None:
            start = min(self._anchor_index, index)
            end = max(self._anchor_index, index)
            self._selected_indices = set(range(start, end + 1))
        elif multi:
            if index in self._selected_indices:
                self._selected_indices.remove(index)
                self._anchor_index = index
            else:
                self._selected_indices.add(index)
                self._anchor_index = index
        else:
            self._selected_indices = {index}
            self._anchor_index = index
        self._notify_selection()

    def select_all(self) -> None:
        self._selected_indices = set(range(len(self._tokens)))
        self._notify_selection()

    def invert_selection(self) -> None:
        all_indices = set(range(len(self._tokens)))
        self._selected_indices = all_indices - self._selected_indices
        self._notify_selection()

    def clear_selection(self) -> None:
        self._selected_indices.clear()
        self._anchor_index = None
        self._notify_selection()

    def delete_selected(self) -> None:
        if not self._selected_indices:
            return
        sorted_indices = sorted(list(self._selected_indices), reverse=True)
        for idx in sorted_indices:
            self.remove_token(idx)
        self.clear_selection()

    def duplicate_token(self, index: int) -> None:
        if 0 <= index < len(self._tokens):
            self.insert_token(index + 1, self._tokens[index])

    def reverse_selection(self) -> None:
        indices = sorted(list(self._selected_indices))
        if len(indices) < 2:
            return
        values = [self._tokens[i] for i in indices]
        values.reverse()
        for i, val in zip(indices, values):
            self._tokens[i] = val
        self._notify_change()

    def join_selection(self, separator: str = " ") -> None:
        indices = sorted(list(self._selected_indices))
        if len(indices) < 2:
            return
        values = [self._tokens[i] for i in indices]
        new_val = separator.join(values)
        first_idx = indices[0]
        self._tokens[first_idx] = new_val
        for i in sorted(indices[1:], reverse=True):
            self._tokens.pop(i)
        self.clear_selection()
        self.select(first_idx)
        self._notify_change()

    def group_selection(
        self, open_char: str, close_char: str, separator: str = " "
    ) -> None:
        indices = sorted(list(self._selected_indices))
        if not indices:
            return
        values = [self._tokens[i] for i in indices]
        joined = separator.join(values)
        new_val = f"{open_char}{joined}{close_char}"
        first_idx = indices[0]
        self._tokens[first_idx] = new_val
        if len(indices) > 1:
            for i in sorted(indices[1:], reverse=True):
                self._tokens.pop(i)
        self.clear_selection()
        self.select(first_idx)
        self._notify_change()

    def _adjust_selection_after_removal(self, index: int) -> None:
        new_selection = set()
        for i in self._selected_indices:
            if i < index:
                new_selection.add(i)
            elif i > index:
                new_selection.add(i - 1)
        self._selected_indices = new_selection

        if self._anchor_index == index:
            self._anchor_index = None
        elif self._anchor_index is not None and self._anchor_index > index:
            self._anchor_index -= 1
        self._notify_selection()

    def _notify_change(self) -> None:
        if self.on_change:
            self.on_change(self._tokens)

    def _notify_selection(self) -> None:
        if self.on_selection_change:
            if self._anchor_index is not None and 0 <= self._anchor_index < len(
                self._tokens
            ):
                self.on_selection_change(
                    self._anchor_index, self._tokens[self._anchor_index]
                )
            else:
                self.on_selection_change(None, "")

    @staticmethod
    def get_token_variant(token: str) -> str:
        if not token:
            return "default"
        if len(token) > 1:
            if (token.startswith("(") and token.endswith(")")) or (
                token.startswith("[") and token.endswith("]")
            ):
                return "special"
            if token.startswith("<") and token.endswith(">"):
                return "special"
            if token.startswith('"') and token.endswith('"'):
                return "special"
        if token in '()[]<>"':
            return "bracket"
        if token in ":,":
            return "separator"
        if token and (token.startswith(("-", ".")) or token[0].isdigit()):
            try:
                if token not in ("-", "."):
                    float(token)
                    return "number"
            except ValueError:
                pass
        return "default"
