from __future__ import annotations

import math
import tkinter as tk
from tkinter import END, INSERT
from typing import Any, Callable, Dict, Optional, Tuple, Union, cast

from ttkbootstrap.publisher import Channel, Publisher

from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n

from .color_manager import ColorManager, ColorOverrides
from .nine_slices import NineSliceRenderer

i18n: I18nManager = get_i18n()


class MEntry(tk.Entry):
    """
    MEntry estilo Flutter com renderização otimizada (Nine-Slice).
    Inclui lógica moderna de input (atalhos, menu de contexto, validação visual)
    e suporte a bootstyle.
    """

    # pylint: disable=too-many-ancestors, too-many-instance-attributes
    # pylint: disable=too-many-arguments, too-many-locals

    def __init__(
        self,
        master: Union[tk.Widget, tk.Tk, tk.Toplevel],
        width: int = 200,
        height: int = 40,
        radius: int = 10,
        bg_color: Optional[str] = None,
        hover_color: Optional[str] = None,
        border_color: Optional[str] = None,
        focus_color: Optional[str] = None,
        error_color: str = "#e74c3c",
        border_width: int = 1,
        padding: Optional[int] = None,
        inc_pad: int = 5,
        elevation: int = 1,
        padx: int = 0,
        pady: int = 0,
        shadow_color: Optional[str] = None,
        password_mode: bool = False,
        read_only: bool = False,
        textvariable: Optional[tk.Variable] = None,
        font: Tuple[str, int] = ("Noto Sans", 10),
        bootstyle: str = "",
        **kwargs: Any,
    ) -> None:
        """
        Logic: Initializes canvas-based entry, color manager, nine-slice
        renderer, and bindings."""
        self.canvas = tk.Canvas(
            master, width=width, height=height, bd=0, highlightthickness=0
        )
        if textvariable is not None:
            kwargs["textvariable"] = textvariable
        super().__init__(master=self.canvas, font=font, **kwargs)
        if padding is None:
            safe_padding = math.ceil(radius * (1 - math.sqrt(2) / 2))
            self.padding = safe_padding + border_width + elevation * 2 + inc_pad
        else:
            self.padding = padding
        self.padxy = (padx, pady)
        overrides: ColorOverrides = {
            "bg": bg_color,
            "border": border_color,
            "hover": hover_color,
            "shadow": shadow_color,
            "focus": focus_color,
        }
        self._is_password = password_mode
        self._is_readonly = read_only
        self._error_color = error_color
        self._draw_job: Optional[str] = None
        self.color_manager = ColorManager(
            master,
            cast(Dict[str, Optional[str]], overrides),
            bootstyle=bootstyle,
        )
        self.renderer = NineSliceRenderer(radius, border_width, elevation)
        self._window_id = self.canvas.create_window(
            width / 2,
            height / 2,
            window=self,
            anchor="center",
            tags="content_window",
        )
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        if hover_color:
            self.canvas.bind("<Enter>", self._on_enter)
            self.canvas.bind("<Leave>", self._on_leave)
            self.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Button-1>", lambda _: self.focus())
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self._setup_functional_bindings()
        self._create_context_menu()
        self._update_state_visuals()
        Publisher.subscribe(
            name=str(id(self)), func=self.on_theme_change, channel=Channel.STD
        )
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.update_appearance()

    def configure(
        self, cnf: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Any:
        """
        Logic: Intercepts configuration changes to update custom properties
        and appearance."""
        full_args = {}
        if cnf:
            full_args.update(cnf)
        full_args.update(kwargs)
        if "state" in full_args:
            state = full_args["state"]
            is_disabled = state == "disabled"
            self.color_manager.set_disabled_state(is_disabled)
            result = super().configure(cnf, **kwargs)
            self.update_appearance()
            return result
        return super().configure(cnf, **kwargs)

    config: Callable[..., Any] = configure

    def update_appearance(self) -> None:
        """Atualiza a aparência usando o sistema de cache global.

        Logic: Refreshes colors and redraws the background."""
        current_colors = self.color_manager.update_palette()
        self.canvas.configure(bg=current_colors["parent"])
        entry_bg = current_colors["bg"]
        self.configure(
            bg=entry_bg,
            highlightthickness=0,
            borderwidth=0,
            disabledbackground=entry_bg,
            readonlybackground=entry_bg,
        )
        if self.renderer.radius > 0:
            self.renderer.generate_slices(current_colors)
        self._redraw_canvas()

    def _schedule_redraw(self) -> None:
        """Agendas a redraw to avoid lag during resize.

        Logic: Debounces redraw."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
        self._draw_job = self.after(10, self._redraw_canvas)

    def _redraw_canvas(self) -> None:
        """Logic: Draws the entry background."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
            self._draw_job = None
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w > 1 and h > 1:
            if self.renderer.radius == 0:
                self.canvas.delete(
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
                self.canvas.delete("bg_rect")
                colors = self.color_manager.palette
                self.canvas.create_rectangle(
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
                self.canvas.delete("bg_rect")
                self.renderer.draw_on_canvas(self.canvas, w, h)
            self.canvas.tag_raise("content_window")

    def on_theme_change(self, _note: Any = None) -> None:
        """Callback disparado quando o tema é alterado.

        Logic: Updates appearance on theme change."""
        if not self.winfo_exists():
            Publisher.unsubscribe(str(id(self)))
            return
        self.update_appearance()

    def _on_destroy(self, _event: tk.Event) -> None:
        """Limpa recursos ao destruir o widget.

        Logic: Cleans up jobs and subscriptions."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
        Publisher.unsubscribe(str(id(self)))

    def _on_focus_in(self, _event: tk.Event) -> None:
        """Manipula evento de ganho de foco.

        Logic: Sets focus state visuals."""
        if self["state"] != "disabled" and (not self._is_readonly):
            self.color_manager.set_focus_state(True)
            self.update_appearance()

    def _on_focus_out(self, _event: tk.Event) -> None:
        """Manipula evento de perda de foco.

        Logic: Unsets focus state visuals."""
        self.color_manager.set_focus_state(False)
        self.update_appearance()

    def _setup_functional_bindings(self) -> None:
        """Configura atalhos de teclado.

        Logic: Binds shortcuts for word deletion, selection,
        and context menu."""
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
        """Logic: Updates visuals for password mode and readonly state."""
        if self._is_password:
            self.configure(show="•")
        else:
            self.configure(show="")
        state = "readonly" if self._is_readonly else "normal"
        if self["state"] != "disabled":
            self.configure(state=state)

    def _delete_word_left(self, _event: tk.Event) -> str:
        """Deleta a palavra à esquerda do cursor.

        Logic: Deletes left word."""
        pos = self.index(INSERT)
        if pos <= 0:
            return "break"
        text = self.get()

        def get_type(char: str) -> int:
            if char == " ":
                return 0
            if char.isalnum() or char == "_":
                return 1
            return 2

        target_type = get_type(text[pos - 1])
        new_pos = pos - 1
        while new_pos > 0 and get_type(text[new_pos - 1]) == target_type:
            new_pos -= 1
        self.delete(new_pos, pos)
        return "break"

    def _delete_word_right(self, _event: tk.Event) -> str:
        """Deleta a palavra à direita do cursor.

        Logic: Deletes right word."""
        text = self.get()
        length = len(text)
        pos = self.index(INSERT)
        if pos >= length:
            return "break"

        def get_type(char: str) -> int:
            if char == " ":
                return 0
            if char.isalnum() or char == "_":
                return 1
            return 2

        target_type = get_type(text[pos])
        new_pos = pos + 1
        while new_pos < length and get_type(text[new_pos]) == target_type:
            new_pos += 1
        self.delete(pos, new_pos)
        return "break"

    def _select_all(self, _event: Optional[tk.Event]) -> str:
        """Seleciona todo o texto.

        Logic: Selects all text."""
        self.select_range(0, END)
        self.icursor(END)
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

        Logic: Replaces all text with clipboard."""
        if not self._is_readonly:
            self.delete(0, END)
            self._paste()

    def _create_context_menu(self) -> None:
        """Cria o menu de contexto.

        Logic: Creates a standard edit menu."""
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
            (
                i18n.get("entry.menu.clear", "Clear"),
                lambda: self.delete(0, END),
            ),
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
        """Exibe o menu de contexto.

        Logic: Shows context menu, updating item states."""
        if not self.winfo_exists():
            return
        lbl_cut = i18n.get("entry.menu.cut", "Cut")
        lbl_copy = i18n.get("entry.menu.copy", "Copy")
        lbl_paste = i18n.get("entry.menu.paste", "Paste")
        lbl_cut_all = i18n.get("entry.menu.cut_all", "Cut All")
        lbl_copy_all = i18n.get("entry.menu.copy_all", "Copy All")
        lbl_replace = i18n.get("entry.menu.replace", "Replace")
        lbl_clear = i18n.get("entry.menu.clear", "Clear")
        has_text = bool(self.get())
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
            has_sel = self.selection_present()
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
        for i in range((self.context_menu.index(END) or 0) + 1):
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
        """Cola o texto da área de transferência.

        Logic: Pastes text."""
        if not self._is_readonly:
            if self.selection_present():
                self.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.event_generate("<<Paste>>")

    def set_text(self, text: str) -> None:
        """Define o texto do campo programaticamente.

        Logic: Replaces current text with new text."""
        state = self["state"]
        if state == "readonly":
            self.configure(state="normal")
        self.delete(0, END)
        self.insert(0, text)
        if state == "readonly":
            self.configure(state="readonly")

    def set_error(self, is_error: bool = True) -> None:
        """Define o estado de erro visual.

        Logic: Triggers error blink animation."""
        if is_error:
            self._blink_counter = 6
            self._blink_animate()
        else:
            self._blink_counter = 0
            self.color_manager.set_temporary_border(None)
            self.update_appearance()

    def _blink_animate(self) -> None:
        """Animação de piscar a borda em caso de erro.

        Logic: Flashes border color."""
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

        Logic: Sets readonly state and visuals."""
        self._is_readonly = active
        self._update_state_visuals()

    def _on_enter(self, _event: tk.Event) -> None:
        """Manipula evento de mouse enter.

        Logic: Sets hover state visuals."""
        if self["state"] != "disabled":
            self.color_manager.set_hover_state(True)
            self.update_appearance()

    def _on_leave(self, _event: tk.Event) -> None:
        """Manipula evento de mouse leave.

        Logic: Unsets hover state visuals."""
        if self["state"] != "disabled":
            self.color_manager.set_hover_state(False)
            self.update_appearance()

    def _on_canvas_resize(self, event: tk.Event) -> None:
        """Redimensiona o conteúdo quando o canvas muda de tamanho.

        Logic: Updates window size and redraws canvas."""
        w, h = (event.width, event.height)
        self.canvas.coords(self._window_id, w / 2, h / 2)
        inner_w = max(1, w - (self.padding + self.padxy[0]) * 2)
        inner_h = max(1, h - (self.padding + self.padxy[1]) * 2)
        self.canvas.itemconfigure(
            self._window_id, width=inner_w, height=inner_h
        )
        self._schedule_redraw()

    def pack(self, **kwargs: Any) -> None:
        """Empacota o widget (Canvas).

        Logic: Packs canvas."""
        self.canvas.pack(**kwargs)

    def grid(self, **kwargs: Any) -> None:
        """Posiciona o widget (Canvas) usando grid.

        Logic: Grids canvas."""
        self.canvas.grid(**kwargs)

    def place(self, **kwargs: Any) -> None:
        """Posiciona o widget (Canvas) usando place.

        Logic: Places canvas."""
        self.canvas.place(**kwargs)

    def pack_forget(self) -> None:
        """Remove o widget do gerenciador pack.

        Logic: Pack forget canvas."""
        self.canvas.pack_forget()

    def grid_forget(self) -> None:
        """Remove o widget do gerenciador grid.

        Logic: Grid forget canvas."""
        self.canvas.grid_forget()

    def place_forget(self) -> None:
        """Remove o widget do gerenciador place.

        Logic: Place forget canvas."""
        self.canvas.place_forget()

    @property
    def m_entry_widget(self) -> tk.Canvas:
        """Retorna o widget Canvas subjacente."""
        return self.canvas

    def get_current_word_pos(self) -> Optional[Tuple[int, int]]:
        """
        Logic: Calculates screen coordinates for the start of
        the current word.
        """
        try:
            pos = self.index(INSERT)
            text = self.get()

            # Calculate Entry's screen position via Canvas
            # This is more robust for embedded widgets inside a Canvas
            c_bbox = self.canvas.bbox(self._window_id)
            if c_bbox:
                entry_x, entry_y, _, _ = c_bbox
                wx = self.canvas.winfo_rootx() + entry_x
                wy = self.canvas.winfo_rooty() + entry_y
            else:
                # Fallback if canvas item not found
                wx = self.winfo_rootx()
                wy = self.winfo_rooty()

            if not text:
                bbox = self._get_bbox(INSERT)
                if bbox:
                    x, y, _, h = bbox
                    return (wx + x, wy + y + h)
                return (wx, wy + self.winfo_height())

            start_pos = pos
            if start_pos > 0:

                def get_type(char: str) -> int:
                    if char == " ":
                        return 0
                    if char.isalnum() or char == "_":
                        return 1
                    return 2

                # Check bounds
                if start_pos - 1 < len(text):
                    target_type = get_type(text[start_pos - 1])
                    while (
                        start_pos > 0
                        and get_type(text[start_pos - 1]) == target_type
                    ):
                        start_pos -= 1

            bbox = self._get_bbox(start_pos)
            if not bbox:
                bbox = self._get_bbox(INSERT)

            if bbox:
                x, y, _, h = bbox
                return (wx + x, wy + y + h)

            return (wx, wy + self.winfo_height())
        except Exception:
            return None

    def _get_bbox(
        self, index: Union[int, str]
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Safe wrapper for bbox that ensures we call the Entry command,
        not grid_bbox.

        Note: tkinter.Misc maps bbox=grid_bbox. While Entry overrides this,
        static analysis and some runtime contexts can confuse the two.
        Direct tcl call avoids this ambiguity.
        """
        try:
            res = self.tk.call(self._w, "bbox", index)
            if res:
                return self._getints(res)
        except tk.TclError:
            pass
        return None
