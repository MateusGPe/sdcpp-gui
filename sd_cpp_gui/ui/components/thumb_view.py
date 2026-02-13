import dataclasses
import logging
import os
import textwrap
import threading
import time
import tkinter as tk
import uuid
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from PIL import Image, ImageDraw, ImageTk
from ttkbootstrap.publisher import Channel, Publisher

from sd_cpp_gui.ui.components.color_manager import ColorManager, blend_colors


@dataclasses.dataclass
class ThumbProps:
    """Properties for a single thumbnail item."""

    id: Any
    image_path: Optional[str]
    description: str = ""
    data: Any = None


@dataclasses.dataclass
class ThumbViewConfig:
    """Configuration for LazzyThumbView appearance and behavior."""

    columns: int = 4
    rows: int = 3
    thumb_width: int = 128
    thumb_height: int = 148
    thumb_padding_x: int = 5
    thumb_padding_y: int = 5
    auto_resize_columns: bool = True

    bg_color: str = "#2E2E2E"
    thumb_bg_color: str = "#3C3C3C"
    thumb_border_color: str = "#505050"
    image_area_bg_color: str = "#333333"

    selected_bg_color: str = "#007ACC"
    selected_border_color: str = "#005F9C"
    focused_border_color: str = "#E879F9"
    hover_bg_color: str = "#4A4A4A"
    hover_border_color: str = "#606060"

    text_color: str = "#E0E0E0"
    selected_text_color: str = "#FFFFFF"
    description_font_family: str = (
        "Segoe UI" if os.name == "nt" else "Helvetica"
    )
    description_font_size: int = 9
    description_lines: int = 2
    show_description: bool = True

    highlight_thickness: int = 2
    scroll_wheel_step: int = 1
    multi_select_modifier: str = "Control"
    range_select_modifier: str = "Shift"
    select_on_focus_change: bool = True
    double_click_interval: int = 300


MODIFIER_MASKS = {
    "Shift": 0x0001,
    "Control": 0x0004,
    "Mod1": 0x0008,
    "Button1": 0x0100,
    "Button2": 0x0200,
    "Button3": 0x0400,
}


class LazzyThumb(tk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        view_config: ThumbViewConfig,
        image_loader_callback: Callable[
            [
                str,
                Tuple[int, int],
                Callable[[Optional[Image.Image], bool], None],
            ],
            None,
        ],
    ):
        super().__init__(
            parent,
            width=view_config.thumb_width,
            height=view_config.thumb_height,
            highlightthickness=view_config.highlight_thickness,
            bd=0,
        )

        self.pack_propagate(False)
        self.grid_propagate(False)

        self.view_config = view_config
        self.image_loader = image_loader_callback
        self.thumb_props: Optional[ThumbProps] = None

        # State
        self._current_image_tk: Optional[ImageTk.PhotoImage] = None
        self._current_assigned_id: Any = None
        self._is_selected: bool = False
        self._is_focused: bool = False
        self._is_hovered: bool = False
        self._is_loaded: bool = False

        # UI Construction
        self.content_frame = tk.Frame(self)
        self.content_frame.pack(expand=True, fill=tk.BOTH, padx=1, pady=1)

        self._image_label = tk.Label(
            self.content_frame, bg=self.view_config.image_area_bg_color
        )
        self._image_label.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

        self._description_label: Optional[tk.Label] = None
        if view_config.show_description:
            self._init_description_label()

        self._bind_events()
        self._update_appearance()

    def _init_description_label(self):
        font = (
            self.view_config.description_font_family,
            self.view_config.description_font_size,
        )
        self._description_label = tk.Label(
            self.content_frame,
            text="",
            font=font,
            wraplength=max(10, self.view_config.thumb_width - 12),
            justify=tk.CENTER,
            anchor=tk.N,
        )
        self._description_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(2, 2))

    def _bind_events(self):
        widgets = [self, self.content_frame, self._image_label]
        if self._description_label:
            widgets.append(self._description_label)

        for w in widgets:
            if not w:
                continue
            w.bind("<Enter>", self._on_mouse_enter, add="+")
            w.bind("<Leave>", self._on_mouse_leave, add="+")
            w.bind("<MouseWheel>", self._propagate_scroll, add="+")
            w.bind(
                "<Button-4>",
                lambda e, d=-1: self._propagate_scroll(e, d),
                add="+",
            )
            w.bind(
                "<Button-5>",
                lambda e, d=1: self._propagate_scroll(e, d),
                add="+",
            )

    def _propagate_scroll(self, event, delta=None):
        if (
            self.master
            and self.master.master
            and hasattr(self.master.master, "_on_mouse_wheel")
        ):
            self.master.master._on_mouse_wheel(event, delta)

    def assign_item(self, thumb_props: Optional[ThumbProps]):
        """Populate this cell with data."""
        self.thumb_props = thumb_props
        self._current_assigned_id = thumb_props.id if thumb_props else None
        self._is_loaded = False

        if not thumb_props:
            self.clear_content()
        else:
            if self._description_label:
                self._set_description(thumb_props.description)
            self._request_image(thumb_props)

        self._update_appearance()

    def _set_description(self, text):
        if not self._description_label:
            return
        avg_char_w = self.view_config.description_font_size * 0.6
        wrap_chars = int((self.view_config.thumb_width - 10) / avg_char_w)
        wrapped = textwrap.fill(
            text,
            width=max(10, wrap_chars),
            max_lines=self.view_config.description_lines,
            placeholder="…",
        )
        self._description_label.config(text=wrapped)

    def _request_image(self, props):
        if not props.image_path:
            self.clear_content(text="No Image")
            return

        # Calculate Size
        desc_h = 0
        if self._description_label:
            desc_h = (
                self.view_config.description_font_size + 6
            ) * self.view_config.description_lines

        w = self.view_config.thumb_width - 4
        h = self.view_config.thumb_height - desc_h - 4

        # Call the injected loader
        # Closure captures the ID to prevent race conditions (async
        # loaded image arriving for old item)
        req_id = self._current_assigned_id

        def on_image_ready(pil_image: Optional[Image.Image], success: bool):
            if not self.winfo_exists() or self._current_assigned_id != req_id:
                return  # Cancelled or superseded

            if pil_image:
                self._current_image_tk = ImageTk.PhotoImage(pil_image)
                self._image_label.config(image=self._current_image_tk, text="")
                self._is_loaded = success
            else:
                self.clear_content(text="Error")

            self._update_appearance()

        self.image_loader(props.image_path, (w, h), on_image_ready)

    def clear_content(self, text=""):
        self._current_image_tk = None
        self._image_label.config(
            image="", text=text, bg=self.view_config.image_area_bg_color
        )
        if self._description_label:
            self._description_label.config(text="")
        self._is_loaded = False

    # --- Visual State ---
    def set_selected(self, val):
        if self._is_selected != val:
            self._is_selected = val
            self._update_appearance()

    def set_focused(self, val):
        if self._is_focused != val:
            self._is_focused = val
            self._update_appearance()

    def _on_mouse_enter(self, e):
        if not self._is_hovered:
            self._is_hovered = True
            self._update_appearance()

    def _on_mouse_leave(self, e):
        if not self.winfo_exists():
            return
        # Check if mouse is strictly outside the widget tree
        x, y = self.winfo_pointerxy()
        under = self.winfo_containing(x, y)
        if str(under).startswith(str(self)):
            return

        if self._is_hovered:
            self._is_hovered = False
            self._update_appearance()

    def _update_appearance(self):
        if not self.winfo_exists():
            return
        cfg = self.view_config

        bg, border = cfg.thumb_bg_color, cfg.thumb_border_color
        txt_fg = cfg.text_color

        if not self.thumb_props:
            bg, border = cfg.bg_color, cfg.bg_color
        elif self._is_selected:
            bg, border = cfg.selected_bg_color, cfg.selected_border_color
            txt_fg = cfg.selected_text_color
        elif self._is_focused:
            border = cfg.focused_border_color

        if self._is_hovered and not self._is_selected and self.thumb_props:
            bg, border = cfg.hover_bg_color, cfg.hover_border_color

        self.config(bg=bg, highlightbackground=border, highlightcolor=border)
        self.content_frame.config(bg=bg)

        # Image area bg: if loaded, match cell, else keep dark placeholder
        img_bg = (
            bg
            if (self._is_loaded and self._current_image_tk)
            else cfg.image_area_bg_color
        )
        self._image_label.config(bg=img_bg, fg=txt_fg)

        if self._description_label:
            self._description_label.config(bg=bg, fg=txt_fg)


# --- Main View ---


class LazzyThumbView(tk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        config: Optional[ThumbViewConfig] = None,
        # Callback signature: (path, (w, h), callback(pil_image, success))
        image_loader: Optional[
            Callable[
                [
                    str,
                    Tuple[int, int],
                    Callable[[Optional[Image.Image], bool], None],
                ],
                None,
            ]
        ] = None,
        on_selection_changed: Optional[
            Callable[[List[ThumbProps]], None]
        ] = None,
        on_item_click: Optional[Callable[[ThumbProps, tk.Event], None]] = None,
        on_item_right_click: Optional[
            Callable[[ThumbProps, tk.Event], None]
        ] = None,
        on_item_double_click: Optional[
            Callable[[ThumbProps, tk.Event], None]
        ] = None,
        bootstyle: str = "",
        **kwargs,
    ):
        if config is None:
            config = ThumbViewConfig()

        super().__init__(parent, **kwargs)

        self._config = config
        self._logger = logging.getLogger("LazzyThumbView")
        self.color_manager = ColorManager(
            self, overrides={}, bootstyle=bootstyle
        )

        # If no loader provided, use internal default
        self._image_loader = (
            image_loader if image_loader else self._default_image_loader
        )

        # Callbacks
        self._on_selection_changed = on_selection_changed
        self._on_item_click = on_item_click
        self._on_item_right_click = on_item_right_click
        self._on_item_double_click = on_item_double_click

        # Data
        self._all_items_map: Dict[Any, ThumbProps] = {}
        self._all_items_ordered: List[ThumbProps] = []
        self._filtered_items: List[ThumbProps] = []

        # UI State
        self._thumb_widgets: List[LazzyThumb] = []
        self._current_offset: int = 0
        self._selected_ids: Set[Any] = set()
        self._focused_id: Optional[Any] = None
        self._anchor_id: Optional[Any] = None
        self._filter_text: str = ""

        # Internals
        self._last_click_time: float = 0.0
        self._last_clicked_id: Optional[Any] = None

        # --- FIXED MODE: Removed resize timer and binding ---
        # self._resize_timer: Optional[str] = None

        self._init_ui()
        self._create_grid()

        # Bindings
        self.config(takefocus=1)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<KeyPress>", self._on_key_press)
        self._thumbs_frame.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        self._thumbs_frame.bind(
            "<Button-4>", lambda e: self._on_mouse_wheel(e, -1), add="+"
        )
        self._thumbs_frame.bind(
            "<Button-5>", lambda e: self._on_mouse_wheel(e, 1), add="+"
        )
        self.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        self.bind("<Button-4>", lambda e: self._on_mouse_wheel(e, -1), add="+")
        self.bind("<Button-5>", lambda e: self._on_mouse_wheel(e, 1), add="+")

        # --- FIXED MODE: Removed Configure Binding ---
        # self.bind("<Configure>", self._on_resize, add="+")

        self.bind("<Destroy>", self._on_destroy, add="+")
        Publisher.subscribe(
            name=str(id(self)), func=self.on_theme_change, channel=Channel.STD
        )
        self._update_theme_colors()

    def _default_image_loader(
        self,
        path: str,
        size: Tuple[int, int],
        callback: Callable[[Optional[Image.Image], bool], None],
    ):
        """Built-in simple threaded loader."""

        def _load():
            try:
                if not path or not os.path.exists(path):
                    self.after(0, callback, None, False)
                    return

                img = Image.open(path)
                img.thumbnail(size, Image.Resampling.BICUBIC)
                self.after(0, callback, img, True)
            except Exception as e:
                self._logger.error(f"Error loading {path}: {e}")
                self.after(0, callback, None, False)

        threading.Thread(target=_load, daemon=True).start()

    def on_theme_change(self, _note=None):
        if not self.winfo_exists():
            Publisher.unsubscribe(str(id(self)))
            return
        self._update_theme_colors()

    def _update_theme_colors(self):
        palette = self.color_manager.update_palette()

        # Update config colors from theme
        self._config.bg_color = palette["parent"]
        self._config.thumb_bg_color = palette["bg"]
        self._config.thumb_border_color = palette["border"]

        primary = self.color_manager._resolve_color("primary")
        self._config.selected_bg_color = primary
        self._config.selected_border_color = primary
        self._config.selected_text_color = self.color_manager.ensure_contrast(
            primary, "#ffffff"
        )
        self._config.focused_border_color = primary

        self._config.hover_bg_color = palette["bg_hover"]
        self._config.hover_border_color = self.color_manager._resolve_color(
            "info"
        )

        self._config.text_color = self.color_manager._resolve_color("fg")

        # Image area background (slightly darker than thumb bg)
        self._config.image_area_bg_color = blend_colors(
            palette["bg"], "#000000", 0.1
        )

        # Apply to self
        self.configure(bg=self._config.bg_color)
        self._thumbs_frame.configure(bg=self._config.bg_color)

        # Refresh all thumbs
        for thumb in self._thumb_widgets:
            thumb._update_appearance()

    def _init_ui(self):
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._thumbs_frame = tk.Frame(self, bg=self._config.bg_color)
        self._thumbs_frame.grid(row=0, column=0, sticky="nsew")
        self._scrollbar = ttk.Scrollbar(
            self, orient=tk.VERTICAL, command=self._on_scrollbar
        )
        self._scrollbar.grid(row=0, column=1, sticky="ns")

    def _on_resize(self, event):
        if not self._config.auto_resize_columns or event.widget != self:
            return
        if self._resize_timer:
            self.after_cancel(self._resize_timer)
        self._resize_timer = self.after(
            100, lambda: self._recalc_cols(event.width)
        )

    def _recalc_cols(self, width):
        if width < 50:
            return
        full_w = self._config.thumb_width + (self._config.thumb_padding_x * 2)
        new_cols = max(1, (width - 20) // full_w)
        if new_cols != self._config.columns:
            self._config.columns = new_cols
            self._create_grid()

    def _create_grid(self):
        for w in self._thumb_widgets:
            w.destroy()
        self._thumb_widgets.clear()

        # Reset grid weights
        for i in range(50):
            self._thumbs_frame.columnconfigure(i, weight=0)
            self._thumbs_frame.rowconfigure(i, weight=0)

        for c in range(self._config.columns):
            self._thumbs_frame.columnconfigure(c, weight=1, uniform="c")
        for r in range(self._config.rows):
            self._thumbs_frame.rowconfigure(r, weight=1, uniform="r")

        count = self._config.rows * self._config.columns
        for i in range(count):
            thumb = LazzyThumb(
                self._thumbs_frame, self._config, self._image_loader
            )
            thumb.grid(
                row=i // self._config.columns,
                column=i % self._config.columns,
                padx=self._config.thumb_padding_x,
                pady=self._config.thumb_padding_y,
                sticky="nsew",
            )
            self._bind_cell(thumb)
            self._thumb_widgets.append(thumb)

        self._layout_items()

    def _bind_cell(self, cell):
        def _recursive_bind(w):
            w.bind(
                "<Button-1>",
                lambda e, t=cell: self._on_cell_click(t, e, False),
                add="+",
            )
            w.bind(
                "<Button-3>",
                lambda e, t=cell: self._on_cell_click(t, e, True),
                add="+",
            )
            for c in w.winfo_children():
                _recursive_bind(c)

        _recursive_bind(cell)

    def _on_destroy(self, e):
        if e.widget == self:
            Publisher.unsubscribe(str(id(self)))
            self._all_items_map.clear()
            self._all_items_ordered.clear()

    # --- Public API ---

    def set_items(self, items: List[ThumbProps]):
        self._all_items_ordered = list(items)
        self._all_items_map = {i.id: i for i in items}
        self._apply_filter()
        self.clear_selection(notify=False)
        self._focused_id = None
        self._current_offset = 0
        self._layout_items()

    def add_items(self, items: List[ThumbProps]):
        for i in items:
            if i.id not in self._all_items_map:
                self._all_items_map[i.id] = i
                self._all_items_ordered.append(i)
        self._apply_filter()
        self._layout_items()

    def remove_items(self, ids: List[Any]):
        id_set = set(ids)
        self._all_items_ordered = [
            i for i in self._all_items_ordered if i.id not in id_set
        ]
        for i in id_set:
            self._all_items_map.pop(i, None)
        self._selected_ids -= id_set
        if self._focused_id in id_set:
            self._focused_id = None
        self._apply_filter()
        self._layout_items()
        self._trigger_selection()

    def filter(self, text: str):
        self._filter_text = text.strip().lower()
        self._apply_filter()
        self._current_offset = 0
        self._layout_items()

    def _apply_filter(self):
        if not self._filter_text:
            self._filtered_items = list(self._all_items_ordered)
        else:
            self._filtered_items = [
                i
                for i in self._all_items_ordered
                if self._filter_text in i.description.lower()
            ]

    def get_selection(self) -> List[ThumbProps]:
        return [
            self._all_items_map[i]
            for i in self._selected_ids
            if i in self._all_items_map
        ]

    def clear_selection(self, notify=True):
        self._selected_ids.clear()
        self._update_visuals()
        if notify:
            self._trigger_selection()

    # --- Interaction ---

    def _on_cell_click(
        self, thumb: LazzyThumb, event: tk.Event, right_click: bool
    ):
        if not thumb.thumb_props:
            return
        self.focus_set()

        iid = thumb.thumb_props.id

        if right_click:
            if iid not in self._selected_ids:
                self._selected_ids = {iid}
                self._focused_id = iid
                self._update_visuals()
                self._trigger_selection()
            if self._on_item_right_click:
                self._on_item_right_click(thumb.thumb_props, event)
            return

        # Double Click Check
        now = time.time() * 1000
        if (
            iid == self._last_clicked_id
            and (now - self._last_click_time)
            < self._config.double_click_interval
        ):
            if self._on_item_double_click:
                self._on_item_double_click(thumb.thumb_props, event)
            return

        self._last_click_time = now
        self._last_clicked_id = iid

        # Selection Logic
        ctrl = (
            event.state & MODIFIER_MASKS[self._config.multi_select_modifier]
        ) != 0
        shift = (
            event.state & MODIFIER_MASKS[self._config.range_select_modifier]
        ) != 0

        if shift and self._anchor_id:
            self._range_select(self._anchor_id, iid, ctrl)
        elif ctrl:
            if iid in self._selected_ids:
                self._selected_ids.remove(iid)
            else:
                self._selected_ids.add(iid)
            self._anchor_id = iid
        else:
            self._selected_ids = {iid}
            self._anchor_id = iid

        self._focused_id = iid
        self._update_visuals()
        self._trigger_selection()

        if self._on_item_click:
            self._on_item_click(thumb.thumb_props, event)

    def _range_select(self, start_id, end_id, keep_existing):
        try:
            # Map IDs to indices in current filtered list
            ids = [i.id for i in self._filtered_items]
            a, b = ids.index(start_id), ids.index(end_id)
            subset = [
                self._filtered_items[i].id
                for i in range(min(a, b), max(a, b) + 1)
            ]

            if not keep_existing:
                self._selected_ids.clear()
            self._selected_ids.update(subset)
        except ValueError:
            self._selected_ids.add(end_id)  # Fallback

    # --- Scrolling & Rendering ---

    def _on_mouse_wheel(self, event, delta=None):
        if not self._filtered_items:
            return "break"
        if delta is None:
            if os.name == "nt":
                delta = -1 if event.delta > 0 else 1
            else:
                delta = -1 if event.num == 4 else 1  # Linux

        step = self._config.scroll_wheel_step * delta * self._config.columns
        self._scroll(step)
        return "break"

    def _scroll(self, delta_items):
        new_off = max(
            0,
            min(
                self._current_offset + delta_items,
                max(0, len(self._filtered_items) - len(self._thumb_widgets)),
            ),
        )
        if new_off != self._current_offset:
            self._current_offset = int(new_off)
            self._layout_items()

    def _on_scrollbar(self, action, value, unit=None):
        if not self._filtered_items:
            return
        total_rows = (
            len(self._filtered_items) + self._config.columns - 1
        ) // self._config.columns
        curr_row = self._current_offset // self._config.columns

        if action == tk.MOVETO:
            target = int(float(value) * max(0, total_rows - self._config.rows))
            self._scroll((target - curr_row) * self._config.columns)
        elif action == tk.SCROLL:
            step = int(value) * (self._config.rows if unit == "pages" else 1)
            self._scroll(step * self._config.columns)

    def _layout_items(self):
        for i, w in enumerate(self._thumb_widgets):
            idx = self._current_offset + i
            if idx < len(self._filtered_items):
                item = self._filtered_items[idx]
                w.assign_item(item)
                w.set_selected(item.id in self._selected_ids)
                w.set_focused(item.id == self._focused_id)
            else:
                w.assign_item(None)
                w.set_selected(False)
                w.set_focused(False)
        self._update_scrollbar()

    def _update_visuals(self):
        """Update selection/focus without reloading content."""
        for w in self._thumb_widgets:
            if w.thumb_props:
                w.set_selected(w.thumb_props.id in self._selected_ids)
                w.set_focused(w.thumb_props.id == self._focused_id)

    def _update_scrollbar(self):
        if not self._scrollbar:
            return
        total = len(self._filtered_items)
        visible = len(self._thumb_widgets)
        if total <= visible:
            self._scrollbar.grid_remove()
        else:
            self._scrollbar.grid()
            top = self._current_offset / total
            btm = (self._current_offset + visible) / total
            self._scrollbar.set(top, btm)

    def _trigger_selection(self):
        if self._on_selection_changed:
            self.after_idle(
                lambda: self._on_selection_changed(self.get_selection())
            )

    # --- Keyboard ---

    def _on_focus_in(self, e):
        if not self._focused_id and self._filtered_items:
            self._focused_id = self._filtered_items[0].id
            self._update_visuals()

    def _on_key_press(self, e):
        if not self._filtered_items:
            return

        # Determine current index
        idx = 0
        if self._focused_id:
            try:
                idx = [x.id for x in self._filtered_items].index(
                    self._focused_id
                )
            except ValueError:
                pass
        else:
            idx = self._current_offset

        k = e.keysym
        cols = self._config.columns

        if k == "Right":
            idx += 1
        elif k == "Left":
            idx -= 1
        elif k == "Down":
            idx += cols
        elif k == "Up":
            idx -= cols
        elif k == "Home":
            idx = 0
        elif k == "End":
            idx = len(self._filtered_items) - 1
        elif k == "space":
            # Toggle Selection
            item = self._filtered_items[
                max(0, min(idx, len(self._filtered_items) - 1))
            ]
            if item.id in self._selected_ids:
                self._selected_ids.remove(item.id)
            else:
                self._selected_ids.add(item.id)
            self._update_visuals()
            self._trigger_selection()
            return "break"
        elif k == "Return" and self._on_item_click:
            item = self._filtered_items[
                max(0, min(idx, len(self._filtered_items) - 1))
            ]
            self._on_item_click(item, e)
            return "break"

        # Clamp and Update
        idx = max(0, min(idx, len(self._filtered_items) - 1))

        # Scroll to view if needed
        page_size = len(self._thumb_widgets)
        if idx < self._current_offset:
            self._current_offset = (idx // cols) * cols
        elif idx >= self._current_offset + page_size:
            row_diff = (idx // cols) - self._config.rows + 1
            self._current_offset = row_diff * cols

        self._focused_id = self._filtered_items[idx].id
        self._layout_items()  # Refresh to show focus and potential scroll

        if self._config.select_on_focus_change and not (
            e.state & MODIFIER_MASKS["Control"]
        ):
            self._selected_ids = {self._focused_id}
            self._trigger_selection()

        return "break"


# --- Independent Demo ---
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Standalone LazzyThumbView")
    root.geometry("800x600")

    # 1. Config
    cfg = ThumbViewConfig(
        thumb_width=140,
        thumb_height=160,
        columns=5,
        rows=4,  # Fixed Config
    )

    # 2. Setup View
    def on_sel(items):
        print(f"Selected: {[i.description for i in items]}")

    view = LazzyThumbView(root, config=cfg, on_selection_changed=on_sel)
    view.pack(fill=tk.BOTH, expand=True)

    # 3. Create Dummy Data
    # Note: Since we use the default loader, we need valid
    # paths or it will show "Error".
    # For this demo, we will create some temp images.

    temp_dir = "temp_demo_thumbs"
    os.makedirs(temp_dir, exist_ok=True)

    items = []
    colors = ["#FF5733", "#33FF57", "#3357FF", "#F1C40F", "#9B59B6"]

    print("Generating demo images...")
    for i in range(50):
        color = colors[i % len(colors)]
        path = os.path.join(temp_dir, f"img_{i}.png")
        if not os.path.exists(path):
            img = Image.new("RGB", (200, 200), color)
            d = ImageDraw.Draw(img)
            d.text((50, 90), str(i), fill="white")
            img.save(path)

        items.append(
            ThumbProps(
                id=uuid.uuid4(),
                image_path=path,
                description=f"Item {i} - {color}",
            )
        )

    view.set_items(items)

    def cleanup():
        try:
            import shutil

            shutil.rmtree(temp_dir)
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", cleanup)
    root.mainloop()
