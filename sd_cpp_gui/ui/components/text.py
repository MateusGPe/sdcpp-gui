from __future__ import annotations

import tkinter as tk
from tkinter import END, INSERT, SEL, ttk
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import ttkbootstrap as tb
from ttkbootstrap.publisher import Channel, Publisher
from ttkbootstrap.style import Colors

from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n

from .color_manager import ColorManager, ColorOverrides
from .nine_slices import NineSliceRenderer

i18n: I18nManager = get_i18n()


class MText(tk.Text):
    """
    MText: Widget de texto multilinha moderno com renderização
    Nine-Slice otimizada.
    """

    # pylint: disable=too-many-ancestors, too-many-instance-attributes, too-many-arguments

    def __init__(
        self,
        master: Union[tk.Widget, tk.Tk, tk.Toplevel],
        width: int = 300,
        height: int = 150,
        radius: int = 10,
        bg_color: Optional[str] = None,
        fg_color: Optional[str] = None,
        hover_color: Optional[str] = None,
        border_color: Optional[str] = None,
        focus_color: Optional[str] = None,
        error_color: str = "#e74c3c",
        border_width: int = 1,
        padding: int = 10,
        elevation: int = 1,
        shadow_color: Optional[str] = None,
        read_only: bool = False,
        font: Tuple[str, int] = ("Noto Sans", 10),
        bootstyle: str = "",
        scrollbar: bool = True,
        autohide: bool = True,
        **kwargs: Any,
    ) -> None:
        """Logic: Initializes canvas-based text widget with nine-slice
        rendering, custom scrolling, and bindings."""
        self._canvas = tk.Canvas(
            master, width=width, height=height, bd=0, highlightthickness=0
        )
        self._internal_frame = tk.Frame(
            self._canvas, bd=0, highlightthickness=0
        )
        self._internal_frame.columnconfigure(0, weight=1)
        self._internal_frame.rowconfigure(0, weight=1)
        kwargs.pop("width", None)
        kwargs.pop("height", None)
        if "undo" not in kwargs:
            kwargs["undo"] = True
        # Explicitly set autoseparators to True for better undo granularity
        if "autoseparators" not in kwargs:
            kwargs["autoseparators"] = True

        super().__init__(master=self._internal_frame, font=font, **kwargs)
        self.config(bd=0, highlightthickness=0)
        if fg_color:
            self.configure(fg=fg_color, insertbackground=fg_color)
        self._scrollbar_widget: Optional[ttk.Scrollbar] = None
        self.autohide = autohide
        self._scrollbar_visible = True
        self._hovering = False
        self._scroll_parent = self.find_scrolling_parent()
        if scrollbar:
            self._scrollbar_widget = ttk.Scrollbar(
                self._internal_frame, orient="vertical", command=self.yview
            )
            self.configure(yscrollcommand=self._on_scroll)
            if not self.autohide:
                self._scrollbar_widget.grid(row=0, column=1, sticky="ns")
            else:
                self._scrollbar_visible = False
        super().grid(row=0, column=0, sticky="nsew")
        self.padding = padding + border_width + elevation
        overrides: ColorOverrides = {
            "bg": bg_color,
            "border": border_color,
            "hover": hover_color,
            "shadow": shadow_color,
            "focus": focus_color,
        }
        self._is_readonly = read_only
        self._error_color = error_color
        self._blink_counter = 0
        self._draw_job: Optional[str] = None
        self.color_manager = ColorManager(
            master,
            cast(Dict[str, Optional[str]], overrides),
            bootstyle=bootstyle,
        )
        self.renderer = NineSliceRenderer(radius, border_width, elevation)
        self._window_id = self._canvas.create_window(
            width / 2,
            height / 2,
            window=self._internal_frame,
            anchor="center",
            tags="content_window",
        )
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<Button-1>", lambda _: self.focus_set())
        self._internal_frame.bind("<Button-1>", lambda _: self.focus_set())
        if hover_color:
            self._canvas.bind("<Enter>", self._on_enter)
            self._canvas.bind("<Leave>", self._on_leave)
            self._internal_frame.bind("<Enter>", self._on_enter)
            self.bind("<Enter>", self._on_enter)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._setup_mousewheel_bindings()
        self._setup_functional_bindings()
        self._create_context_menu()
        self._update_state_visuals()
        Publisher.subscribe(
            name=str(id(self)), func=self.on_theme_change, channel=Channel.STD
        )
        self.update_appearance()

    def update_appearance(self) -> None:
        """Atualiza a aparência do widget via Renderer.

        Logic: Updates colors and re-renders the nine-slice background."""
        current_colors = self.color_manager.update_palette()
        self._canvas.configure(bg=current_colors["parent"])
        entry_bg = current_colors["bg"]
        self.configure(bg=entry_bg)
        self._internal_frame.configure(bg=entry_bg)
        if not self.color_manager.overrides.get("fg"):
            try:
                style = tb.Style.get_instance() or tb.Style()
                fg = cast(Colors, style.colors).inputfg
                self.configure(
                    fg=fg,
                    insertbackground=fg,
                    borderwidth=0,
                    highlightthickness=0,
                )
            except Exception:
                self.configure(borderwidth=0, highlightthickness=0)
        if self.renderer.radius > 0:
            self.renderer.generate_slices(current_colors)
        self._redraw_canvas()

    def _schedule_redraw(self) -> None:
        """Agendas a redraw to avoid lag during resize.

        Logic: Debounces redraw call."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
        self._draw_job = self.after(10, self._redraw_canvas)

    def _redraw_canvas(self) -> None:
        """Desenha o background otimizado.

        Logic: Draws the background using the nine-slice renderer."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
            self._draw_job = None
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w > 1 and h > 1:
            if self.renderer.radius == 0:
                self._canvas.delete(
                    "ns_c",
                    "ns_tl",
                    "ns_tr",
                    "ns_bl",
                    "ns_br",
                    "ns_t",
                    "ns_b",
                    "ns_l",
                    "ns_r",
                )
                self._canvas.delete("bg_rect")
                colors = self.color_manager.palette
                self._canvas.create_rectangle(
                    0,
                    0,
                    w,
                    h,
                    fill=colors["bg"],
                    outline=colors["border"],
                    width=self.renderer.border_width,
                    tags="bg_rect",
                )
            else:
                self._canvas.delete("bg_rect")
                self.renderer.draw_on_canvas(self._canvas, w, h)
            self._canvas.tag_raise("content_window")

    def on_theme_change(self, _note: Any = None) -> None:
        """Logic: Updates appearance on theme change."""
        if not self.winfo_exists():
            Publisher.unsubscribe(str(id(self)))
            return
        self.update_appearance()

    def _on_destroy(self, _event: tk.Event) -> None:
        """Logic: Cleans up resources and unsubscribes events on destroy."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
        Publisher.unsubscribe(str(id(self)))

    def _on_focus_in(self, _event: tk.Event) -> None:
        """Logic: Sets focus state visuals."""
        if self["state"] != "disabled" and (not self._is_readonly):
            self.color_manager.set_focus_state(True)
            self.update_appearance()

    def _on_focus_out(self, _event: tk.Event) -> None:
        """Logic: Unsets focus state visuals."""
        self.color_manager.set_focus_state(False)
        self.update_appearance()

    def _setup_functional_bindings(self) -> None:
        """Logic: Binds shortcuts for deletion, selection, and context menu."""
        self.bind("<Control-BackSpace>", self._delete_word_left)
        self.bind("<Control-Delete>", self._delete_word_right)
        self.bind("<Control-a>", self._select_all)
        trigger = (
            "<Button-2>"
            if self.tk.call("tk", "windowingsystem") == "aqua"
            else "<Button-3>"
        )
        self.bind(trigger, self._show_context_menu)

    def _update_state_visuals(self) -> None:
        """Logic: Updates widget state (disabled/normal)."""
        state = "disabled" if self._is_readonly else "normal"
        if self["state"] != "disabled" or self._is_readonly:
            self.config(state=state)

    def _delete_word_left(self, _event: tk.Event) -> str:
        """Logic: Implements Ctrl+Backspace behavior."""
        if self._is_readonly:
            return "break"
        self.delete("insert -1c wordstart", "insert")
        return "break"

    def _delete_word_right(self, _event: tk.Event) -> str:
        """Logic: Implements Ctrl+Delete behavior."""
        if self._is_readonly:
            return "break"
        self.delete("insert", "insert wordend")
        return "break"

    def _select_all(self, _event: Optional[tk.Event]) -> str:
        """Logic: Selects all text."""
        self.tag_add(SEL, "1.0", END)
        self.mark_set(INSERT, "1.0")
        self.see(INSERT)
        return "break"

    def _cut_all(self) -> None:
        """Recorta todo o conteúdo.

        Logic: Cuts all text."""
        if not self._is_readonly:
            self._select_all(None)
            self.event_generate("<<Cut>>")

    def _copy_all(self) -> None:
        """Copia todo o conteúdo.

        Logic: Copies all text."""
        self._select_all(None)
        self.event_generate("<<Copy>>")

    def _replace_all(self) -> None:
        """Substitui todo o conteúdo pelo da área de transferência.

        Logic: Replaces all text with clipboard content."""
        if not self._is_readonly:
            self.delete("1.0", END)
            self._paste()

    def _create_context_menu(self) -> None:
        """Logic: Creates a standard edit context menu."""
        self.context_menu = tk.Menu(self, tearoff=0)
        actions = [
            (i18n.get("entry.menu.cut", "Cut"), "<<Cut>>"),
            (i18n.get("entry.menu.copy", "Copy"), "<<Copy>>"),
            (i18n.get("entry.menu.paste", "Paste"), self._paste),
            None,
            (i18n.get("entry.menu.cut_all", "Cut All"), self._cut_all),
            (i18n.get("entry.menu.copy_all", "Copy All"), self._copy_all),
            (i18n.get("entry.menu.replace", "Replace"), self._replace_all),
            None,
            (
                i18n.get("entry.menu.select_all", "Select All"),
                lambda: self._select_all(None),
            ),
            (i18n.get("entry.menu.clear", "Clear"), self.clear),
        ]
        for item in actions:
            if item is None:
                self.context_menu.add_separator()
            else:
                _lbl, cmd = item

                def func(c: Any = cmd) -> Any:
                    return self.event_generate(c) if isinstance(c, str) else c()

                self.context_menu.add_command(label=_lbl, command=func)

    def _show_context_menu(self, event: tk.Event) -> None:
        """Logic: Displays context menu, enabling/disabling items
        based on state."""
        lbl_cut = i18n.get("entry.menu.cut", "Cut")
        lbl_copy = i18n.get("entry.menu.copy", "Copy")
        lbl_paste = i18n.get("entry.menu.paste", "Paste")
        lbl_cut_all = i18n.get("entry.menu.cut_all", "Cut All")
        lbl_copy_all = i18n.get("entry.menu.copy_all", "Copy All")
        lbl_replace = i18n.get("entry.menu.replace", "Replace")
        lbl_clear = i18n.get("entry.menu.clear", "Clear")
        has_text = bool(self.get("1.0", "end-1c"))
        if self._is_readonly:
            state_map = {
                lbl_cut: False,
                lbl_copy: True,
                lbl_paste: False,
                lbl_cut_all: False,
                lbl_copy_all: has_text,
                lbl_replace: False,
                lbl_clear: False,
            }
        else:
            try:
                has_sel = bool(self.tag_ranges(SEL))
            except Exception:
                has_sel = False
            try:
                has_clip = bool(self.clipboard_get())
            except tk.TclError:
                has_clip = False
            state_map = {
                lbl_cut: has_sel,
                lbl_copy: has_sel,
                lbl_paste: has_clip,
                lbl_cut_all: has_text,
                lbl_copy_all: has_text,
                lbl_replace: has_clip,
                lbl_clear: True,
            }
        last_index = self.context_menu.index(END)
        if last_index is None:
            return
        for i in range(last_index + 1):
            try:
                _lbl = self.context_menu.entrycget(i, "label")
                if _lbl in state_map:
                    self.context_menu.entryconfigure(
                        i, state="normal" if state_map[_lbl] else "disabled"
                    )
            except tk.TclError:
                pass
        self.context_menu.tk_popup(event.x_root + 1, event.y_root + 1)

    def _paste(self) -> None:
        """
        Logic: Pastes clipboard content.
        Uses event generation to ensure bindings in
        subclasses (like PromptHighlighter) catch the event.
        """
        if not self._is_readonly:
            self.event_generate("<<Paste>>")

    def _on_scroll(self, first: float, last: float) -> None:
        """Logic: Handles scrollbar updates and autohide logic."""
        first_f = float(first)
        last_f = float(last)
        if self._scrollbar_widget:
            self._scrollbar_widget.set(str(first), str(last))
        if not self.autohide or not self._scrollbar_widget:
            return
        if not self._hovering:
            self._toggle_scrollbar(False)
            return
        is_fully_visible = first_f <= 0.0 and last_f >= 1.0
        self._toggle_scrollbar(not is_fully_visible)

    def _toggle_scrollbar(self, show: bool) -> None:
        """Logic: Shows or hides the scrollbar widget."""
        if self._scrollbar_widget and self._scrollbar_visible != show:
            if show:
                self._scrollbar_widget.grid(row=0, column=1, sticky="ns")
                self._scrollbar_visible = True
            else:
                self._scrollbar_widget.grid_remove()
                self._scrollbar_visible = False

    def set_text(self, text: str) -> None:
        """Logic: Replaces current text with new text."""
        was_readonly = self._is_readonly
        if was_readonly:
            self.config(state="normal")
        self.delete("1.0", END)
        self.insert("1.0", text)
        if was_readonly:
            self.config(state="disabled")

    def get_text(self) -> str:
        """Retorna o texto do widget.

        Logic: Returns all text."""
        return self.get("1.0", "end-1c")

    def clear(self) -> None:
        """Limpa o texto do widget.

        Logic: Deletes all text."""
        self.delete("1.0", END)

    def set_error(self, is_error: bool = True) -> None:
        """Define o estado de erro.

        Logic: Triggers error blink animation."""
        if is_error:
            self._blink_counter = 6
            self._blink_animate()
        else:
            self._blink_counter = 0
            self.color_manager.set_temporary_border(None)
            self.update_appearance()

    def _blink_animate(self) -> None:
        """Logic: Animates border color flashing for error state."""
        if self._blink_counter <= 0:
            self.color_manager.set_temporary_border(None)
            self.update_appearance()
            return
        if self._blink_counter % 2 == 0:
            self.color_manager.set_temporary_border(self._error_color)
        else:
            self.color_manager.set_temporary_border(None)
        self.update_appearance()
        self._blink_counter -= 1
        self.after(150, self._blink_animate)

    def set_readonly(self, active: bool) -> None:
        """Define o modo somente leitura.

        Logic: Sets readonly state and updates visuals."""
        self._is_readonly = active
        self._update_state_visuals()

    def _on_enter(self, _event: tk.Event) -> None:
        """Logic: Sets hover state visuals."""
        if self["state"] != "disabled":
            self.color_manager.set_hover_state(True)
            self.update_appearance()

    def _on_leave(self, _event: tk.Event) -> None:
        """Logic: Unsets hover state visuals."""
        if self["state"] != "disabled":
            self.color_manager.set_hover_state(False)
            self.update_appearance()

    def _setup_mousewheel_bindings(self) -> None:
        """Configura bindings de mousewheel inspirados no SmoothScrollFrame.

        Logic: Binds mousewheel events for smooth scrolling."""
        widgets: List[tk.Misc] = [self._canvas, self._internal_frame, self]
        if self._scrollbar_widget:
            widgets.append(self._scrollbar_widget)
        for widget in widgets:
            widget.bind("<Enter>", self._bound_to_mousewheel, add="+")
            widget.bind("<Leave>", self._unbound_to_mousewheel, add="+")

    def find_scrolling_parent(self) -> Any:
        """Logic: Traverses parents to find a scrollable container."""
        current: Optional[tk.Misc] = self.master
        while current is not None:
            if hasattr(current, "enable_scrolling") and hasattr(
                current, "disable_scrolling"
            ):
                return current
            current = getattr(current, "master", None)
        return None

    def _bound_to_mousewheel(self, _event: tk.Event) -> None:
        """Ativa o scroll quando o mouse entra na área.

        Logic: Binds global mousewheel events to this widget and disables
        parent scrolling."""
        self._hovering = True
        if self._scrollbar_widget is None:
            return
        first, last = self._scrollbar_widget.get()[:2]
        is_fully_visible = float(first) <= 0.0 and float(last) >= 1.0
        self._toggle_scrollbar(not is_fully_visible)
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", self._on_mousewheel)
        self.bind_all("<Button-5>", self._on_mousewheel)
        if self._scroll_parent and (not is_fully_visible):
            self._scroll_parent.disable_scrolling()

    def _unbound_to_mousewheel(self, event: tk.Event) -> None:
        """Desativa o scroll quando o mouse sai.

        Logic: Unbinds global mousewheel events and re-enables
        parent scrolling."""
        try:
            under = self.winfo_containing(event.x_root, event.y_root)
            widgets: List[tk.Misc] = [self._canvas, self._internal_frame, self]
            if self._scrollbar_widget:
                widgets.append(self._scrollbar_widget)
            if under in widgets:
                return
        except Exception:
            pass
        self._hovering = False
        self._toggle_scrollbar(False)
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")
        if self._scroll_parent:
            self._scroll_parent.enable_scrolling()

    def _on_mousewheel(self, event: tk.Event) -> str:
        """Lógica de rolagem suave.

        Logic: Handles vertical scrolling based on event delta."""
        if not self.winfo_exists():
            return "break"
        first, last = self.yview()
        if float(first) <= 0.0 and float(last) >= 1.0:
            return "break"
        if event.delta:
            if abs(event.delta) >= 120:
                self.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                self.yview_scroll(-1 if event.delta > 0 else 1, "units")
        elif event.num == 4:
            self.yview_scroll(-1, "units")
        elif event.num == 5:
            self.yview_scroll(1, "units")
        return "break"

    def _on_canvas_resize(self, event: tk.Event) -> None:
        """Logic: Resizes internal window and triggers redraw."""
        w, h = (event.width, event.height)
        self._canvas.coords(self._window_id, w / 2, h / 2)
        inner_w = max(1, w - self.padding * 2)
        inner_h = max(1, h - self.padding * 2)
        self._canvas.itemconfigure(
            self._window_id, width=inner_w, height=inner_h
        )
        self._schedule_redraw()

    def pack(self, **kwargs: Any) -> None:
        """Logic: Packs the underlying canvas."""
        self._canvas.pack(**kwargs)

    def grid(self, **kwargs: Any) -> None:
        """Logic: Grids the underlying canvas."""
        self._canvas.grid(**kwargs)

    def place(self, **kwargs: Any) -> None:
        """Logic: Places the underlying canvas."""
        self._canvas.place(**kwargs)

    def pack_forget(self) -> None:
        """Logic: Pack forget canvas."""
        self._canvas.pack_forget()

    def grid_forget(self) -> None:
        """Logic: Grid forget canvas."""
        self._canvas.grid_forget()

    def place_forget(self) -> None:
        """Logic: Place forget canvas."""
        self._canvas.place_forget()

    @property
    def m_widget(self) -> tk.Canvas:
        """Retorna o widget Canvas subjacente.

        Logic: Returns canvas."""
        return self._canvas
