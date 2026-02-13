from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional

import ttkbootstrap as ttk

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.domain.services.autocomplete_service import AutocompleteService
from sd_cpp_gui.ui.components.color_manager import ColorManager, blend_colors
from sd_cpp_gui.ui.components.prompt_highlighter import PromptHighlighter
from sd_cpp_gui.ui.components.token_list_model import TokenListModel
from sd_cpp_gui.ui.components.virtual_chip import VirtualChip


class TokenListView:
    """
    Handles the rendering and interaction of tokens on the canvas.
    """

    def __init__(
        self,
        parent_canvas: tk.Canvas,
        model: TokenListModel,
        color_manager: ColorManager,
        on_focus_request: Callable[[], None],
        allow_drag: bool = True,
        allow_multi_selection: bool = True,
        on_right_click: Optional[Callable[[int, tk.Event], None]] = None,
        on_double_click: Optional[Callable[[int, tk.Event], None]] = None,
        on_scroll_event: Optional[Callable[[int, int, tk.Event], None]] = None,
        on_background_right_click: Optional[Callable[[tk.Event], None]] = None,
        autocomplete_service: Optional[AutocompleteService] = None,
        alignment: str = "left",
    ):
        self.parent_canvas = parent_canvas
        self.model = model
        self.cm = color_manager
        self.on_focus_request = on_focus_request
        self.allow_drag = allow_drag
        self.allow_multi_selection = allow_multi_selection
        self.on_right_click = on_right_click
        self.on_double_click = on_double_click
        self.on_scroll_event = on_scroll_event
        self.on_background_right_click = on_background_right_click
        self.alignment = alignment
        self._last_reflow_width = 0
        self._last_total_height = 0
        self._editor_window_id: Optional[int] = None
        self._editing_index: Optional[int] = None
        self._scroll_jobs: dict[int, str] = {}
        self._scroll_accumulators: dict[int, float] = {}

        self.chips: List[VirtualChip] = []
        self.chip_pool: List[VirtualChip] = []
        self._drag_data = {
            "item_idx": None,
            "x": 0,
            "y": 0,
            "widget": None,
            "chip": None,
            "target_idx": None,
            "ghost": None,
            "potential_drag": None,
        }
        self.padding = 8

        # Inner Canvas & Scrollbar
        self.chip_canvas = tk.Canvas(
            self.parent_canvas, bd=0, highlightthickness=0, height=60
        )
        self.scrollbar = ttk.Scrollbar(
            self.parent_canvas,
            orient="vertical",
            command=self.chip_canvas.yview,
        )
        self.chip_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.chip_canvas.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
            padx=(self.padding, self.padding),
            pady=self.padding,
        )

        self._bind_events()

        # Initialize reusable editor
        self._editor = PromptHighlighter(
            self.chip_canvas,
            height=1,
            font=(SYSTEM_FONT, 9),
            highlightthickness=0,
            radius=0,
            border_width=0,
            elevation=0,
            padding=0,
            autocomplete_service=autocomplete_service,
        )
        self._editor.bind("<Return>", self._on_editor_return, add="+")
        self._editor.bind("<Escape>", self._on_editor_escape, add="+")
        self._editor.bind("<FocusOut>", self._on_editor_focus_out, add="+")

    def _bind_events(self):
        self.chip_canvas.bind("<Motion>", self._on_canvas_motion)
        self.chip_canvas.bind("<Button-1>", self._on_canvas_click)
        self.chip_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.chip_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.chip_canvas.bind("<Button-3>", self._on_canvas_right_click)
        if self.chip_canvas.tk.call("tk", "windowingsystem") == "aqua":
            self.chip_canvas.bind("<Button-2>", self._on_canvas_right_click)
        self.chip_canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.chip_canvas.bind("<Leave>", self._on_canvas_leave)
        self.chip_canvas.bind("<Configure>", self._on_chip_canvas_configure)
        self.chip_canvas.bind("<Enter>", self._bind_mousewheel)
        self.chip_canvas.bind("<Leave>", self._unbind_mousewheel)

    def update_style(self):
        colors = self.cm.palette
        self.chip_canvas.configure(bg=colors["bg"])
        for chip in self.chips:
            self._draw_chip(chip)

    def set_alignment(self, alignment: str) -> None:
        self.alignment = alignment
        self._reflow()

    def sync_chips(self):
        tokens = self.model.tokens
        count_tokens = len(tokens)

        while len(self.chips) < count_tokens:
            if self.chip_pool:
                chip = self.chip_pool.pop()
                chip.set_visible(self.chip_canvas, True)
            else:
                chip = VirtualChip("", "default", (SYSTEM_FONT, 8))
            self.chips.append(chip)

        while len(self.chips) > count_tokens:
            chip = self.chips.pop()
            chip.set_visible(self.chip_canvas, False)
            self.chip_pool.append(chip)

        for i, token in enumerate(tokens):
            chip = self.chips[i]
            variant = self.model.get_token_variant(token)

            if chip.text != token or chip.variant != variant:
                chip.text = token
                chip.variant = variant
                chip.update_size()

            is_selected = i in self.model.selected_indices
            if chip.selected != is_selected:
                chip.selected = is_selected
                self._draw_chip(chip)

        self.chip_canvas.after(10, self._reflow)

    def _reflow(self, event: Optional[tk.Event] = None) -> None:
        parent_height = 0
        if event:
            width = event.width
            parent_height = event.height
        else:
            width = self.chip_canvas.winfo_width()
            parent_height = self.chip_canvas.winfo_height()

        if width < 50:
            return

        if (
            event
            and abs(width - self._last_reflow_width) < 5
            and self._last_total_height > 0
        ):
            total_height = self._last_total_height
        else:
            self._last_reflow_width = width
            x, y = 0, 0
            line_height = 0
            pad_x, pad_y = 4, 4

            # 1. Group chips into lines
            lines: List[List[VirtualChip]] = []
            current_line: List[VirtualChip] = []
            current_line_width = 0

            for chip in self.chips:
                chip.update_size(max_width=width - pad_x)
                added_width = chip.w + (pad_x if current_line else 0)

                if current_line and (current_line_width + added_width > width):
                    lines.append(current_line)
                    current_line = [chip]
                    current_line_width = chip.w
                else:
                    current_line.append(chip)
                    current_line_width += added_width

            if current_line:
                lines.append(current_line)

            # 2. Position chips
            for i, line_chips in enumerate(lines):
                line_height = max(c.h for c in line_chips)
                total_w = sum(c.w for c in line_chips)
                gap = pad_x
                x = 0

                if self.alignment == "center":
                    x = (width - (total_w + (len(line_chips) - 1) * gap)) / 2
                elif self.alignment == "right":
                    x = width - (total_w + (len(line_chips) - 1) * gap)
                elif (
                    self.alignment == "justify"
                    and i < len(lines) - 1
                    and len(line_chips) > 1
                ):
                    gap = (width - total_w) / (len(line_chips) - 1)
                elif (
                    self.alignment == "fill"
                    and i < len(lines) - 1
                    and len(line_chips) > 0
                ):
                    available = width - total_w - (len(line_chips) - 1) * gap
                    if available > 0:
                        extra = available / len(line_chips)
                        for chip in line_chips:
                            chip.w += extra

                for chip in line_chips:
                    chip.x = max(0, x)
                    chip.y = y
                    self._draw_chip(chip)
                    x += chip.w + gap
                y += line_height + pad_y

            total_height = y
            self._last_total_height = total_height
            self.chip_canvas.configure(scrollregion=(0, 0, width, total_height))

        if total_height > parent_height and parent_height > 1:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(
                    side=tk.RIGHT,
                    fill=tk.Y,
                    padx=(0, self.padding),
                    pady=self.padding,
                    before=self.chip_canvas,
                )
                self.chip_canvas.pack_configure(padx=(self.padding, 0))
        elif self.scrollbar.winfo_ismapped():
            if total_height < parent_height - 5:
                self.scrollbar.pack_forget()
                self.chip_canvas.pack_configure(
                    padx=(self.padding, self.padding)
                )

    def _get_chip_colors(self, chip: VirtualChip) -> dict:
        p = self.cm.palette
        container_bg = p["bg"]
        primary = self.cm._resolve_color("primary")
        fg_default = self.cm._resolve_color("fg")
        target_bg = None
        if chip.variant != "default":
            if chip.variant == "number":
                target_bg = self.cm._resolve_color("success")
            elif chip.variant == "bracket":
                target_bg = self.cm._resolve_color("warning")
            elif chip.variant == "special":
                target_bg = self.cm._resolve_color("info")
            elif chip.variant == "separator":
                target_bg = self.cm._resolve_color("danger")
        if target_bg:
            base_bg = target_bg
        else:
            base_bg = blend_colors(fg_default, container_bg, 0.1)
        if chip.dragging:
            bg_color = blend_colors(primary, container_bg, 0.6)
            fg_color = self.cm.ensure_contrast(bg_color, fg_default)
            border_color = bg_color
        elif chip.drop_target:
            bg_color = blend_colors(primary, container_bg, 0.3)
            fg_color = self.cm.ensure_contrast(bg_color, fg_default)
            border_color = primary
        elif chip.selected:
            bg_color = blend_colors(base_bg, primary, 0.6)
            fg_color = self.cm.ensure_contrast(bg_color, primary)
            border_color = primary
        elif chip.hovering:
            bg_color = blend_colors(primary, base_bg, 0.2)
            fg_color = self.cm.ensure_contrast(bg_color, fg_default)
            border_color = bg_color
        else:
            bg_color = base_bg
            fg_color = self.cm.ensure_contrast(bg_color, fg_default)
            border_color = base_bg
        return {
            "bg": bg_color,
            "bg_base": bg_color,
            "bg_hover": bg_color,
            "border": border_color,
            "shadow": "#000000",
            "parent": container_bg,
            "fg": fg_color,
        }

    def _draw_chip(self, chip: VirtualChip) -> None:
        colors = self._get_chip_colors(chip)
        chip.renderer.generate_slices(colors)
        chip.renderer.draw_on_canvas(
            self.chip_canvas,
            chip.w,
            chip.h,
            tag_prefix=chip.tag_prefix,
            x=chip.x,
            y=chip.y,
        )
        text_tag = f"{chip.tag_prefix}_text"
        text_kwargs = (
            {"width": chip.wrap_width} if chip.wrap_width else {"width": 0}
        )
        if self.chip_canvas.find_withtag(text_tag):
            self.chip_canvas.itemconfigure(
                text_tag,
                text=chip.text,
                fill=colors["fg"],
                font=chip.font,
                **text_kwargs,
            )
            self.chip_canvas.coords(text_tag, chip.x + 10, chip.y + chip.h / 2)
        else:
            self.chip_canvas.create_text(
                chip.x + 10,
                chip.y + chip.h / 2,
                text=chip.text,
                anchor="w",
                fill=colors["fg"],
                font=chip.font,
                tags=text_tag,
                **text_kwargs,
            )
        close_tag = f"{chip.tag_prefix}_close"
        close_font = (
            chip.font[0],
            max(chip.font[1] - 1, 6) if len(chip.font) > 2 else 8,
        )
        if self.chip_canvas.find_withtag(close_tag):
            self.chip_canvas.itemconfigure(
                close_tag, fill=colors["fg"], font=close_font
            )
            self.chip_canvas.coords(
                close_tag, chip.x + chip.w - 10, chip.y + chip.h / 2 - 1
            )
        else:
            self.chip_canvas.create_text(
                chip.x + chip.w - 10,
                chip.y + chip.h / 2 - 1,
                text="×",
                anchor="e",
                fill=colors["fg"],
                font=close_font,
                tags=close_tag,
            )

    def _find_chip_at(self, x: int, y: int) -> Optional[VirtualChip]:
        cx = self.chip_canvas.canvasx(x)
        cy = self.chip_canvas.canvasy(y)
        for chip in self.chips:
            if (
                chip.x <= cx <= chip.x + chip.w
                and chip.y <= cy <= chip.y + chip.h
            ):
                return chip
        return None

    def _on_canvas_click(self, event: tk.Event) -> None:
        self.on_focus_request()
        chip = self._find_chip_at(event.x, event.y)
        if not chip:
            self.model.clear_selection()
            self.sync_chips()
            return

        cx = self.chip_canvas.canvasx(event.x)
        if cx >= chip.x + chip.w - 20:
            self.model.remove_token(self.chips.index(chip))
            self.sync_chips()
        else:
            idx = self.chips.index(chip)
            ctrl = (event.state & 0x0004) or (event.state & 0x20000)
            shift = event.state & 0x0001
            self.model.select(
                idx,
                multi=self.allow_multi_selection and ctrl,
                range_select=self.allow_multi_selection and shift,
            )
            self.sync_chips()
            if self.allow_drag:
                self._drag_data["potential_drag"] = (chip, event.x, event.y)

    def _on_canvas_drag(self, event: tk.Event) -> None:
        if self._drag_data["item_idx"] is None:
            pot = self._drag_data.get("potential_drag")
            if pot:
                chip, start_x, start_y = pot
                if (abs(event.x - start_x) > 5) or (abs(event.y - start_y) > 5):
                    self._start_drag(event, chip)
                    self._drag_data["potential_drag"] = None
                else:
                    return
            else:
                return

        if self.chip_canvas["cursor"] != "fleur":
            self.chip_canvas.configure(cursor="fleur")

        ghost = self._drag_data.get("ghost")
        if ghost and ghost.winfo_exists():
            ghost.geometry(f"+{event.x_root + 1}+{event.y_root + 1}")

        idx = self._drag_data["item_idx"]
        target_idx = None
        cx = self.chip_canvas.canvasx(event.x)
        cy = self.chip_canvas.canvasy(event.y)

        for i, chip in enumerate(self.chips):
            if i == idx:
                continue
            if (
                chip.x <= cx <= chip.x + chip.w
                and chip.y <= cy <= chip.y + chip.h
            ):
                target_idx = i
                break

        prev_target = self._drag_data.get("target_idx")
        if target_idx != prev_target:
            if prev_target is not None and 0 <= prev_target < len(self.chips):
                self.chips[prev_target].drop_target = False
                self._draw_chip(self.chips[prev_target])
            if target_idx is not None:
                self.chips[target_idx].drop_target = True
                self._draw_chip(self.chips[target_idx])
            self._drag_data["target_idx"] = target_idx

    def _start_drag(self, event: tk.Event, chip: VirtualChip) -> None:
        if not self.allow_drag:
            return
        try:
            index = self.chips.index(chip)
        except ValueError:
            return
        self._drag_data["item_idx"] = index
        self._drag_data["widget"] = event.widget
        self._drag_data["chip"] = chip
        self._drag_data["target_idx"] = None
        chip.dragging = True
        self._draw_chip(chip)
        ghost = tk.Toplevel(self.chip_canvas)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.7)
        ghost.attributes("-topmost", True)
        colors = self._get_chip_colors(chip)
        lbl = tk.Label(
            ghost,
            text=chip.text,
            bg=colors["bg"],
            fg=colors["fg"],
            font=chip.font,
            padx=10,
            pady=4,
            relief="solid",
            bd=1,
        )
        lbl.pack()
        ghost.geometry(f"+{event.x_root + 1}+{event.y_root + 1}")
        self._drag_data["ghost"] = ghost

    def _on_canvas_release(self, event: tk.Event) -> None:
        self._drag_data["potential_drag"] = None
        idx = self._drag_data["item_idx"]
        if idx is None:
            return
        self.chip_canvas.configure(cursor="arrow")
        chip = self._drag_data.get("chip")
        if chip:
            chip.dragging = False
        ghost = self._drag_data.get("ghost")
        if ghost:
            ghost.destroy()
        self._drag_data["ghost"] = None
        target_idx = self._drag_data.get("target_idx")
        if target_idx is not None and 0 <= target_idx < len(self.chips):
            self.chips[target_idx].drop_target = False

        if target_idx is not None and target_idx != idx:
            self.model.move_token(idx, target_idx)
            self.sync_chips()
        else:
            self.sync_chips()

        self._drag_data["item_idx"] = None
        self._drag_data["target_idx"] = None
        self._drag_data["widget"] = None

    def _on_canvas_motion(self, event: tk.Event) -> None:
        chip = self._find_chip_at(event.x, event.y)
        for c in self.chips:
            if c == chip:
                if not c.hovering:
                    c.hovering = True
                    self._draw_chip(c)
            elif c.hovering:
                c.hovering = False
                self._draw_chip(c)
        if chip:
            cx = self.chip_canvas.canvasx(event.x)
            if cx >= chip.x + chip.w - 20:
                self.chip_canvas.configure(cursor="hand2")
            else:
                self.chip_canvas.configure(cursor="arrow")
        else:
            self.chip_canvas.configure(cursor="arrow")

    def _on_canvas_leave(self, event: tk.Event) -> None:
        for c in self.chips:
            if c.hovering:
                c.hovering = False
                self._draw_chip(c)

    def _on_canvas_right_click(self, event: tk.Event) -> None:
        chip = self._find_chip_at(event.x, event.y)
        if chip and self.on_right_click:
            self.on_right_click(self.chips.index(chip), event)
        elif not chip and self.on_background_right_click:
            self.on_background_right_click(event)

    def _on_canvas_double_click(self, event: tk.Event) -> None:
        chip = self._find_chip_at(event.x, event.y)
        if chip:
            if self.on_double_click:
                self.on_double_click(self.chips.index(chip), event)
            else:
                self._start_editing(chip, self.chips.index(chip))

    def _on_chip_canvas_configure(self, event: tk.Event) -> None:
        self._reflow(event)

    def _bind_mousewheel(self, event: tk.Event) -> None:
        self.chip_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.chip_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.chip_canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event: tk.Event) -> None:
        self.chip_canvas.unbind_all("<MouseWheel>")
        self.chip_canvas.unbind_all("<Button-4>")
        self.chip_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        try:
            ex = event.x_root - self.chip_canvas.winfo_rootx()
            ey = event.y_root - self.chip_canvas.winfo_rooty()
            chip = self._find_chip_at(ex, ey)
            if chip:
                delta = 0
                if event.num == 4 or event.delta > 0:
                    delta = 1
                elif event.num == 5 or event.delta < 0:
                    delta = -1
                if delta != 0:
                    index = self.chips.index(chip)
                    if self.on_scroll_event:
                        self.on_scroll_event(index, delta, event)
                        return
                    if (event.state & 0x0001) and self.model.get_token_variant(
                        self.model.tokens[index]
                    ) == "number":
                        self._on_chip_scroll(event, chip, index)
                        return
        except Exception:
            pass
        if not self.scrollbar.winfo_ismapped():
            return
        if event.num == 4:
            self.chip_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.chip_canvas.yview_scroll(1, "units")
        else:
            self.chip_canvas.yview_scroll(
                int(-1 * (event.delta / 120)), "units"
            )

    def _on_chip_scroll(
        self, event: tk.Event, chip: VirtualChip, index: int
    ) -> None:
        token = self.model.tokens[index]
        try:
            float(token)  # Validate it is a number
            step = 1 if "." not in token else 0.01
            delta = 0
            if event.num == 4 or event.delta > 0:
                delta = step
            elif event.num == 5 or event.delta < 0:
                delta = -step
            if delta == 0:
                return

            current_acc = self._scroll_accumulators.get(index, 0.0)
            self._scroll_accumulators[index] = current_acc + delta

            if index in self._scroll_jobs:
                self.chip_canvas.after_cancel(self._scroll_jobs[index])

            self._scroll_jobs[index] = self.chip_canvas.after(
                50, lambda: self._apply_scroll_delta(index)
            )
        except ValueError:
            pass

    def _apply_scroll_delta(self, index: int) -> None:
        if index in self._scroll_jobs:
            del self._scroll_jobs[index]

        delta = self._scroll_accumulators.pop(index, 0.0)

        if index < 0 or index >= len(self.model.tokens):
            return

        token = self.model.tokens[index]
        try:
            val = float(token)
            new_val = val + delta
            step = 1 if "." not in token else 0.01
            if step == 1:
                new_token = str(int(new_val))
            else:
                new_token = f"{new_val:.4f}".rstrip("0")
                if new_token.endswith("."):
                    new_token += "0"
            self.model.update_token(index, new_token)
            self.sync_chips()
        except ValueError:
            pass

    def _start_editing(self, chip: VirtualChip, index: int) -> None:
        if self._editor_window_id:
            self._commit_edit()

        self._editing_index = index
        colors = self._get_chip_colors(chip)

        self._editor.color_manager.overrides = colors.copy()
        self._editor.update_appearance()
        self._editor.update_tag_colors()

        self._editor.set_text(chip.text)
        self._editor.highlight()
        self._editor.tag_add("sel", "1.0", "end")
        self._editor.mark_set("insert", "end")

        self._editor_window_id = self.chip_canvas.create_window(
            chip.x,
            chip.y,
            window=self._editor.m_widget,
            anchor="nw",
            width=chip.w,
            height=chip.h,
            tags="editor_window",
        )
        self._editor.focus_set()

    def _commit_edit(self, refocus: bool = True) -> None:
        if not self._editor_window_id:
            return

        new_text = self._editor.get_text().strip()
        index = self._editing_index
        self._cancel_edit(refocus=refocus)

        if index is not None and 0 <= index < len(self.model.tokens):
            if not new_text:
                self.model.remove_token(index)
                self.sync_chips()
            else:
                current_text = self.model.tokens[index]
                if new_text != current_text:
                    self.model.update_token(index, new_text)
                    self.sync_chips()

    def _cancel_edit(self, refocus: bool = True) -> None:
        if self._editor_window_id:
            self.chip_canvas.delete(self._editor_window_id)
            self._editor_window_id = None
            self._editing_index = None
        if refocus:
            self.on_focus_request()

    def _on_editor_return(self, event: tk.Event) -> str:
        self._commit_edit()
        return "break"

    def _on_editor_escape(self, event: tk.Event) -> str:
        self._cancel_edit()
        return "break"

    def _on_editor_focus_out(self, event: tk.Event) -> None:
        self._commit_edit(refocus=False)
