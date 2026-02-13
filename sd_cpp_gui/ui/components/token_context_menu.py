from __future__ import annotations

import re
import tkinter as tk
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from sd_cpp_gui.ui.components.draggable_token_list import DraggableTokenList


class TokenContextMenu:
    def __init__(self, owner: DraggableTokenList) -> None:
        self.owner = owner
        self.ac_svr = owner.autocomplete_service

    @staticmethod
    def split_tokens(token: str) -> List[str]:
        """
        Cleans SD syntax (brackets, weights) and splits into raw word fragments.
        Example: "(masterpiece:1.2)" -> ["masterpiece"]
        """
        if not token:
            return []
        base = re.sub(r"[()\[\]{}<>]|(:[\d.]+)", "", token).strip()
        return [t for t in re.split(r"[\s,.|]+", base) if t]

    def show(self, index: int, event: tk.Event) -> None:
        self._ensure_selection(index)
        indices, is_sequential = self._get_selection_state()

        menu = tk.Menu(self.owner, tearoff=0)
        self._build_standard_actions(menu)

        count = len(indices)
        if count == 1:
            self._build_single_selection_actions(menu, indices[0])
        elif count > 1:
            self._build_multi_selection_actions(menu, indices, is_sequential)

        menu.tk_popup(event.x_root + 1, event.y_root + 1)

    def _ensure_selection(self, index: int) -> None:
        """Ensures the clicked item is selected."""
        if index not in self.owner.model.selected_indices:
            self.owner.model.clear_selection()
            self.owner.model.select(index)
            self.owner.view.sync_chips()

    def _get_selection_state(self) -> Tuple[List[int], bool]:
        """Returns sorted indices and whether they are sequential."""
        indices = sorted(list(self.owner.model.selected_indices))
        count = len(indices)
        is_sequential = False
        if count > 1:
            is_sequential = all(
                indices[i] == indices[i - 1] + 1 for i in range(1, count)
            )
        return indices, is_sequential

    def _build_standard_actions(self, menu: tk.Menu) -> None:
        """Adds Cut, Copy, Delete actions."""
        menu.add_command(label="Cut", command=self.owner._cut_selection)
        menu.add_command(label="Copy", command=self.owner._copy_selection)
        menu.add_command(label="Delete", command=self.owner._delete_selection)
        menu.add_separator()

    def _build_single_selection_actions(
        self, menu: tk.Menu, index: int
    ) -> None:
        """Adds actions specific to a single selected token."""
        menu.add_command(
            label="Duplicate",
            command=lambda: self.owner._duplicate_selection(index),
        )

        prev_sug, next_sug = self._get_surrounding_suggestions(index)

        self._add_insert_submenu(
            menu, "Insert Before", index, prev_sug, is_before=True
        )
        self._add_insert_submenu(
            menu, "Insert After", index, next_sug, is_before=False
        )

        self._add_advanced_suggestions(menu, index)

    def _get_surrounding_suggestions(
        self, index: int
    ) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
        """Fetches probability-based suggestions for previous and next words."""
        prev_suggestions = []
        next_suggestions = []

        if self.ac_svr:
            token = self.owner.model.tokens[index]
            tokens = TokenContextMenu.split_tokens(token)
            if tokens:
                try:
                    prev_suggestions = self.ac_svr.get_previous_prob(
                        tokens[0], limit=5
                    )
                    next_suggestions = self.ac_svr.get_next_prob(
                        tokens[-1], limit=5
                    )
                except Exception:
                    pass
        return prev_suggestions, next_suggestions

    def _add_insert_submenu(
        self,
        menu: tk.Menu,
        label: str,
        index: int,
        suggestions: List[Tuple[str, float]],
        is_before: bool,
    ) -> None:
        """Adds 'Insert Before/After' menu item or submenu."""
        offset = 0 if is_before else 1
        target_idx = index + offset

        if suggestions:
            sub = tk.Menu(menu, tearoff=0)
            for word, prob in suggestions:
                sub.add_command(
                    label=f"{word} ({prob:.0%})",
                    command=lambda w=word: self.owner.insert_token(
                        target_idx, w
                    ),
                )
            sub.add_separator()
            sub.add_command(
                label="Custom...",
                command=lambda: self.owner._insert_placeholder(target_idx),
            )
            menu.add_cascade(label=label, menu=sub)
        else:
            menu.add_command(
                label=label,
                command=lambda: self.owner._insert_placeholder(target_idx),
            )

    def _build_multi_selection_actions(
        self, menu: tk.Menu, indices: List[int], is_sequential: bool
    ) -> None:
        """Adds actions for multiple selected tokens."""
        menu.add_command(
            label="Reverse Order",
            command=lambda: self.owner._reverse_selection(indices),
        )

        if is_sequential:
            menu.add_separator()
            menu.add_command(
                label="Join",
                command=lambda: self.owner._join_selection(indices),
            )
            menu.add_command(
                label="Group ( )",
                command=lambda: self.owner._group_selection(indices, "(", ")"),
            )
            menu.add_command(
                label="Group [ ]",
                command=lambda: self.owner._group_selection(indices, "[", "]"),
            )

        if len(indices) == 2:
            self._add_bridge_suggestions(menu, indices)

    def _add_bridge_suggestions(
        self, menu: tk.Menu, indices: List[int]
    ) -> None:
        """Adds bridge word suggestions between two tokens."""
        if not self.ac_svr:
            return

        t1 = self.owner.model.tokens[indices[0]]
        t2 = self.owner.model.tokens[indices[1]]
        tc1 = TokenContextMenu.split_tokens(t1)
        tc2 = TokenContextMenu.split_tokens(t2)

        if tc1 and tc2:
            c1, c2 = tc1[-1], tc2[0]
            try:
                bridges = self.ac_svr.get_bridge_words(c1, c2)
                if bridges:
                    menu.add_separator()
                    bridge_menu = tk.Menu(menu, tearoff=0)
                    for bridge, _ in bridges:
                        bridge_menu.add_command(
                            label=bridge,
                            command=lambda b=bridge: self.owner.insert_token(
                                indices[1], b
                            ),
                        )
                    menu.add_cascade(label="Insert Bridge", menu=bridge_menu)
            except Exception:
                pass

    def _add_advanced_suggestions(self, menu: tk.Menu, index: int) -> None:
        """Adds advanced suggestions (Next Word, Phrases) submenu."""
        if not self.ac_svr:
            return

        token = self.owner.model.tokens[index]
        tokens = TokenContextMenu.split_tokens(token)
        if not tokens:
            return

        try:
            clean_token = tokens[-1]
            next_words = self.ac_svr.get_next_prob(clean_token, limit=5)
            trigrams = list(self.ac_svr.suggest_trigrams(clean_token, limit=5))

            if not next_words and not trigrams:
                return

            menu.add_separator()
            suggestions_menu = tk.Menu(menu, tearoff=0)

            if next_words:
                suggestions_menu.add_command(
                    label="--- Next Word ---", state="disabled"
                )
                for word, prob in next_words:
                    suggestions_menu.add_command(
                        label=f"{word} ({prob:.0%})",
                        command=lambda w=word: self.owner._insert_token_after(
                            index, w
                        ),
                    )

            if trigrams:
                if next_words:
                    suggestions_menu.add_separator()
                suggestions_menu.add_command(
                    label="--- Phrases ---", state="disabled"
                )
                for item in trigrams:
                    phrase = f"{token} {item['next']}"
                    replace = self.owner._replace_with_phrase
                    suggestions_menu.add_command(
                        label=phrase,
                        command=lambda p=phrase: replace(index, p),
                    )

            menu.add_cascade(label="Suggestions", menu=suggestions_menu)

        except Exception:
            pass
