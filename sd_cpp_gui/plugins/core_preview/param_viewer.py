from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.constants import END

from sd_cpp_gui.constants import CORNER_RADIUS, SYSTEM_FONT
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.ui.components import text
from sd_cpp_gui.ui.components.prompt_highlighter import PromptHighlighter
from sd_cpp_gui.ui.components.utils import CopyLabel

if TYPE_CHECKING:
    from sd_cpp_gui.domain.generation.commands_loader import CommandLoader
    from sd_cpp_gui.infrastructure.i18n import I18nManager

i18n: I18nManager = get_i18n()


class ParamViewer(ttk.Frame):
    """Handles the display of generation parameters and prompts."""

    def __init__(
        self,
        parent: Any,
        cmd_loader: CommandLoader,
        side_color: str,
        **kwargs: Any,
    ) -> None:
        """Logic: Initializes viewer."""
        super().__init__(parent, bootstyle=side_color, **kwargs)
        self.cmd_loader = cmd_loader
        self.side_color = side_color
        self.style = ttk.Style.get_instance()
        self.params: Dict[str, Dict[str, Any]] = {}
        self._param_timer: Optional[str] = None
        self.category_map: Dict[str, str] = {}
        self._build_category_map()
        self._init_ui()

    def _get_current_bg(self) -> str:
        """Logic: Gets current bg color."""
        color_name = self.side_color
        if hasattr(self.style.colors, color_name):
            return getattr(self.style.colors, color_name)
        return self.style.colors.bg

    def _init_ui(self) -> None:
        """Logic: Builds UI."""
        self.columnconfigure((0, 1), weight=1, minsize=100)
        self.rowconfigure(0, weight=1, minsize=100)
        self.f_prompts = ttk.Frame(self, bootstyle=self.side_color)
        self.f_prompts.grid(
            column=0, row=0, sticky="nsew", padx=10, pady=(10, 2)
        )
        current_bg = self._get_current_bg()
        self.prompt_label = CopyLabel(
            self.f_prompts,
            text="PROMPTS",
            font=(SYSTEM_FONT, 10, "bold"),
            bootstyle="primary",
            background=current_bg,
        )
        self.prompt_label.pack(anchor="w", padx=(0, 10), pady=(10, 2))
        self.prompt_preview = PromptHighlighter(
            self.f_prompts,
            height=180,
            font=(SYSTEM_FONT, 10),
            read_only=True,
            bg_color=current_bg,
            bootstyle=self.side_color,
            border_width=0,
            elevation=0,
            padding=0,
        )
        self.prompt_preview.pack(fill=tk.BOTH, expand=True)
        self.txt_params = text.MText(
            self,
            width=300,
            height=300,
            font=(SYSTEM_FONT, 10),
            read_only=True,
            bootstyle=self.side_color,
            bg_color=current_bg,
            border_width=0,
            radius=CORNER_RADIUS,
            elevation=0,
            padding=0,
            wrap=tk.WORD,
        )
        self.txt_params.grid(column=1, row=0, sticky="nsew", padx=10)
        self.txt_params.bind("<Configure>", self._update_text_tabs)
        self._setup_params_tags()

    def update_theme(self, side_color: str) -> None:
        """Logic: Updates theme."""
        self.side_color = side_color
        self.configure(bootstyle=side_color)
        self.f_prompts.configure(bootstyle=side_color)
        self.prompt_preview.color_manager.bootstyle = side_color
        self.prompt_preview.update_appearance()
        current_bg = self._get_current_bg()
        self.prompt_label.configure(background=current_bg)
        self.prompt_preview.color_manager.bootstyle = side_color
        self.prompt_preview.color_manager.palette["bg"] = current_bg
        self.prompt_preview.color_manager.overrides["bg"] = current_bg
        self.prompt_preview.update_appearance()
        self.prompt_preview.configure(background=current_bg)
        self.txt_params.color_manager.bootstyle = side_color
        self.txt_params.color_manager.palette["bg"] = current_bg
        self.txt_params.color_manager.overrides["bg"] = current_bg
        self.txt_params.update_appearance()
        self.txt_params.configure(background=current_bg)
        self._display_current_params()

    def _update_text_tabs(self, event: tk.Event) -> None:
        """Logic: Updates text tabs."""
        w = event.width
        col_w = w // 2 - 20
        total_w = col_w * 2
        start = (w - total_w) // 2 if w > total_w else 10
        if start > 0 and col_w > 0:
            self.txt_params.configure(tabs=(start, start + col_w))

    def _setup_params_tags(self) -> None:
        """Logic: Sets up tags."""
        primary = self.style.colors.primary
        secondary = self.style.colors.secondary
        fg = self.style.colors.fg
        self.txt_params.tag_configure(
            "header",
            font=(SYSTEM_FONT, 10, "bold"),
            foreground=primary,
            spacing1=15,
            spacing3=10,
        )
        self.txt_params.tag_configure(
            "key", font=(SYSTEM_FONT, 9), foreground=secondary, spacing1=10
        )
        self.txt_params.tag_configure(
            "val", font=(SYSTEM_FONT, 9, "bold"), foreground=fg, spacing1=10
        )

    def _build_category_map(self) -> None:
        """Logic: Builds category map."""
        self.category_map = {}
        categorized = self.cmd_loader.get_categorized_commands()
        for cat_key, cmds in categorized.items():
            cat_label = self.cmd_loader.get_category_label(cat_key)
            for cmd in cmds:
                if flag := cmd.get("flag"):
                    for f in flag.split(","):
                        self.category_map[f.strip()] = cat_label
        ignored_categories = {
            "Prompts": ["-p", "--prompt", "-n", "--negative-prompt"],
            "Input": ["-i", "--init-img", "--strength"],
            "LoRA": ["--lora-model-dir"],
            "Embeddings": ["--embd-dir"],
        }
        for cat, flags in ignored_categories.items():
            for flag in flags:
                self.category_map[flag] = cat

    def _get_category(self, flag: str) -> str:
        """Logic: Gets category."""
        return self.category_map.get(flag, "Settings")

    def sync_with_state(self, full_state: Dict[str, Any]) -> None:
        """Logic: Syncs with state."""
        self.params = {}
        for flag, val in full_state.get("parameters", {}).items():
            cmd = self.cmd_loader.get_by_flag(flag)
            name = cmd["name"] if cmd else flag
            self.params[flag] = {"name": name, "value": val}
        p_cmd = self.cmd_loader.get_by_internal_name("Prompt")
        if p_cmd:
            self.params[p_cmd["flag"]] = {
                "name": p_cmd["name"],
                "value": full_state.get("prompt", ""),
            }
        n_cmd = self.cmd_loader.get_by_internal_name("Negative Prompt")
        if n_cmd:
            self.params[n_cmd["flag"]] = {
                "name": n_cmd["name"],
                "value": full_state.get("negative_prompt", ""),
            }
        if self._param_timer:
            self.after_cancel(self._param_timer)
        self._param_timer = self.after(200, self._display_current_params)

    def _display_current_params(self) -> None:
        """Logic: Displays params."""
        pos_prompt = ""
        neg_prompt = ""
        grouped: Dict[str, List[Tuple[str, Any]]] = {}
        prompt_cmd = self.cmd_loader.get_by_internal_name("Prompt")
        neg_cmd = self.cmd_loader.get_by_internal_name("Negative Prompt")
        prompt_flags = (
            set(prompt_cmd["flag"].split(","))
            if prompt_cmd
            else {"-p", "--prompt"}
        )
        neg_flags = (
            set(neg_cmd["flag"].split(","))
            if neg_cmd
            else {"-n", "--negative-prompt"}
        )
        unique_params = {
            (flag, data.get("name")): data
            for flag, data in self.params.items()
            if flag
        }
        for (flag, name), data in unique_params.items():
            val = data.get("value", "")
            if flag in prompt_flags:
                pos_prompt = str(val)
            elif flag in neg_flags:
                neg_prompt = str(val)
            else:
                cat = self._get_category(flag)
                if cat not in grouped:
                    grouped[cat] = []
                grouped[cat].append((str(data.get("name", flag)), val))
        full_text = pos_prompt
        if neg_prompt:
            full_text += f"\n\nNEGATIVE:\n{neg_prompt}"
        if self.prompt_preview.get_text().strip() != full_text.strip():
            self.prompt_preview.set_text(full_text)
        self.txt_params.configure(state="normal")
        self.txt_params.delete("1.0", END)
        if not grouped and (not full_text):
            self.txt_params.insert(
                END, i18n.get("preview.no_params", "No params."), "key"
            )
            self.txt_params.configure(state="disabled")
            return
        cat_order = [
            "Prompts",
            "Input",
            "Dimensions",
            "Sampling",
            "System",
            "LoRA",
            "Embeddings",
        ]
        sorted_cats = sorted(
            grouped.keys(),
            key=lambda k: cat_order.index(k) if k in cat_order else 999,
        )
        for cat in sorted_cats:
            self.txt_params.insert(END, f"{cat.upper()}\n", "header")
            items = sorted(grouped[cat], key=lambda x: x[0])
            for i in range(0, len(items), 2):
                self._insert_param_pair(items[i])
                if i + 1 < len(items):
                    self._insert_param_pair(items[i + 1], newline=True)
                else:
                    self.txt_params.insert(END, "\n")
            self.txt_params.insert(END, "\n")
        self.txt_params.configure(state="disabled")

    def _insert_param_pair(
        self, item: Tuple[str, Any], newline: bool = False
    ) -> None:
        """Logic: Inserts param pair."""
        name, val = item
        self.txt_params.insert(END, "\t")
        self.txt_params.insert(END, f"{name}: ", "key")
        if isinstance(val, bool):
            val = "Enabled"
        self.txt_params.insert(END, f"{val}", "val")
        if newline:
            self.txt_params.insert(END, "\n")
