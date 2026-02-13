"""
Componente de botão customizado estilo 'Flat' - VERSÃO SIMPLIFICADA E ESTÁVEL.
Foco em estabilidade: sem animações, lógica direta e confiável.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as Font
from typing import Any, Callable, Dict, Optional, Tuple, TypedDict, Union, cast

import ttkbootstrap as ttkb
from ttkbootstrap.publisher import Channel, Publisher
from ttkbootstrap.style import Colors

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.infrastructure.logger import get_logger

from .color_manager import ColorManager, blend_colors
from .nine_slices import NineSliceRenderer

logger = get_logger("RoundedButton")


class ButtonPalette(TypedDict):
    fg: str
    text: str
    hover: str
    pressed: str
    disabled_bg: str
    disabled_fg: str


class ButtonColorManager(ColorManager):
    """Gerenciador de cores especializado para botões."""

    def __init__(
        self, master: tk.Misc, overrides: Dict[str, Any], bootstyle: str
    ) -> None:
        """Logic: Initializes button specific color manager."""
        super().__init__(master, overrides, bootstyle)
        self.text_override: Optional[str] = None
        self.button_palette: ButtonPalette = {
            "fg": "#3b8ed0",
            "text": "#ffffff",
            "hover": "#3b8ed0",
            "pressed": "#3b8ed0",
            "disabled_bg": "#cccccc",
            "disabled_fg": "#999999",
        }

    def update_button_colors(self, variant: str) -> None:
        """
        Calcula todas as cores do botão baseado no estado atual e overrides.

        Logic: Resolves button colors (fg, text, hover, pressed) based on
        style and variant."""
        style_colors = self._get_bootstyle_colors(self.bootstyle)
        p = self.button_palette
        overrides = self.overrides
        fg = overrides.get("bg") or style_colors.get("fg", "#3b8ed0")
        p["fg"] = self._resolve_color(fg)
        text_col = self.text_override
        if not text_col:
            if variant == "outlined":
                text_col = p["fg"]
            else:
                style = ttkb.Style.get_instance() or ttkb.Style()
                text_col = cast(Colors, style.colors).get_foreground(
                    self.bootstyle
                )
        p["text"] = self._resolve_color(text_col)
        if overrides.get("hover"):
            p["hover"] = self._resolve_color(overrides["hover"])
        elif variant == "outlined":
            p["hover"] = blend_colors(p["fg"], self.palette["parent"], 0.1)
        else:
            p["hover"] = blend_colors(p["fg"], "#ffffff", 0.85)
        p["pressed"] = blend_colors(
            p["fg"], "#000000", 0.85 if variant == "filled" else 0.7
        )
        p["disabled_bg"] = blend_colors(p["fg"], self.palette["parent"], 0.3)
        p["disabled_fg"] = blend_colors(p["text"], self.palette["parent"], 0.5)

    def _get_bootstyle_colors(self, bootstyle: str) -> Dict[str, str]:
        """Obtém cores do bootstyle.

        Logic: Extracts color hex code from bootstyle name."""
        try:
            style = ttkb.Style.get_instance() or ttkb.Style()
            color_name = (
                bootstyle.lower().split(".")[0]
                if "." in bootstyle
                else bootstyle
            )
            if not color_name or color_name == "default":
                color_name = "primary"
            if hasattr(style.colors, color_name):
                return {"fg": getattr(style.colors, color_name)}
            colors: Colors = cast(Colors, style.colors)
            val = colors.get(color_name)
            return {"fg": val} if val else {"fg": colors.primary}
        except AttributeError:
            return {"fg": "#3b8ed0"}


class RoundedButton(tk.Canvas):
    """
    Botão estilo Flet/Moderno com backend gráfico otimizado (Nine-Slice Tiling).
    """

    def __init__(
        self,
        master: Union[tk.Widget, tk.Tk, tk.Toplevel],
        text: str = "",
        command: Optional[Callable[[], None]] = None,
        width: Optional[int] = None,
        height: int = 40,
        corner_radius: int = 8,
        fg_color: Optional[str] = None,
        text_color: Optional[str] = None,
        hover_color: Optional[str] = None,
        variant: str = "filled",
        font: Union[Tuple[str, int], Tuple[str, int, str]] = (SYSTEM_FONT, 11),
        border_width: int = 0,
        bootstyle: str = "primary",
        cursor: str = "hand2",
        padding: Tuple[int, int] = (20, 0),
        state: str = "normal",
        anchor: str = "center",
        elevation: int = 2,
    ) -> None:
        """
        Logic: Initializes canvas button, color manager, renderer,
        bindings, and draws initial state."""
        self._req_height = height
        self._req_width = width
        super().__init__(master, bd=0, highlightthickness=0)
        self.color_manager = ButtonColorManager(
            master,
            {
                "bg": fg_color,
                "hover": hover_color,
                "border": None,
                "shadow": None,
                "focus": None,
            },
            bootstyle,
        )
        if text_color:
            self.color_manager.text_override = text_color
        self.color_manager.update_palette()
        self.configure(bg=self.color_manager.palette["parent"])
        self.text = text
        self.command = command
        self.variant = variant
        self.font = font
        self.corner_radius = corner_radius
        self.border_width = border_width
        self.padding = padding
        self._anchor = anchor
        self.bootstyle = bootstyle
        self._state = state
        self._draw_job: Optional[str] = None
        self._is_hovering = False
        self._is_pressed = False
        self.color_manager.update_button_colors(self.variant)
        Publisher.subscribe(
            name=str(id(self)), func=self.on_theme_change, channel=Channel.STD
        )
        self._renderer = NineSliceRenderer(
            radius=corner_radius, border_width=border_width, elevation=elevation
        )
        self._configure_initial_size()
        self.configure(cursor=cursor)
        self.bind("<Configure>", self._on_resize)
        self._setup_bindings()
        self._draw()

    def _setup_bindings(self) -> None:
        """Logic: Binds mouse events based on state."""
        state = getattr(self, "_state", None)
        if state in ["normal", "enabled"]:
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
            self.bind("<Button-1>", self._on_press)
            self.bind("<ButtonRelease-1>", self._on_release)
        elif state:
            self.unbind("<Enter>")
            self.unbind("<Leave>")
            self.unbind("<Button-1>")
            self.unbind("<ButtonRelease-1>")

    def configure(
        self, cnf: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Any:
        """Configuração simplificada e direta.

        Logic: Updates configuration properties, handles redrawing/resizing
        triggers."""
        redraw = False
        resize = False
        target_w = self._req_width
        target_h = self._req_height
        if "font" in kwargs:
            self.font = kwargs.pop("font")
            redraw = True
        if "text" in kwargs and (text := kwargs.pop("text")) != self.text:
            self.text = text
            if self._req_width is None and "width" not in kwargs:
                self._configure_initial_size()
                target_w = self._get_button_width()
            redraw = True
        if "state" in kwargs:
            new_state = kwargs.pop("state")
            if new_state and new_state != self._state:
                self._state = new_state
                self._is_hovering = False
                self._is_pressed = False
                self.configure(
                    cursor=""
                    if new_state == "disabled"
                    else kwargs.get("cursor", self.cget("cursor"))
                )
            redraw = True
        nslices_args = {
            "corner_radius": "radius",
            "border_width": "border_width",
            "radius": "radius",
            "borderwidth": "border_width",
            "elevation": "elevation",
        }
        for key, value in nslices_args.items():
            if key in kwargs:
                setattr(self._renderer, value, kwargs.pop(key))
                redraw = True
        style_keys = [
            "bootstyle",
            "fg_color",
            "variant",
            "text_color",
            "anchor",
            "hover_color",
            "padding",
        ]
        if any((k in kwargs for k in style_keys)):
            self.bootstyle = kwargs.pop("bootstyle", self.bootstyle)
            self.color_manager.bootstyle = self.bootstyle
            self._anchor = kwargs.pop("anchor", self._anchor)
            self.variant = kwargs.pop("variant", self.variant)
            if "fg_color" in kwargs:
                self.color_manager.overrides["bg"] = kwargs.pop("fg_color")
            if "hover_color" in kwargs:
                self.color_manager.overrides["hover"] = kwargs.pop(
                    "hover_color"
                )
            if "text_color" in kwargs:
                self.color_manager.text_override = kwargs.pop("text_color")
            if "padding" in kwargs:
                self.padding = kwargs.pop("padding")
            self.color_manager.update_button_colors(self.variant)
            self.color_manager.update_palette()
            redraw = True
        if "width" in kwargs:
            self._req_width = kwargs.get("width") or self._get_button_width()
            kwargs["width"] = self._req_width
            target_w = self._req_width
            resize = True
        if "height" in kwargs:
            self._req_height = kwargs.get("height") or self._req_height
            target_h = self._req_height
            resize = True
        ret = None
        if kwargs:
            ret = super().configure(cnf, **kwargs)
        if resize or redraw:
            self._setup_bindings()
            draw_w = target_w
            if draw_w is not None and self.winfo_exists():
                draw_w = max(draw_w, self.winfo_width())
            self._draw(draw_w, target_h)
        return ret

    config: Callable[..., Any] = configure  # type: ignore

    def cget(self, key: str) -> Any:
        """Retorna valores de configuração.

        Logic: Returns value for given configuration key."""
        if key == "state":
            return self._state
        if key == "text":
            return self.text
        return super().cget(key)

    def _get_button_width(self) -> int:
        """Calcula a largura do texto.

        Logic: Measures text width."""
        font_obj = Font.Font(font=self.font)
        return font_obj.measure(self.text) + self.padding[0] * 2

    def _configure_initial_size(self) -> None:
        """Calcula o tamanho inicial do botão.

        Logic: Sets initial width/height."""
        content_width = self._get_button_width()
        final_width = self._req_width if self._req_width else content_width
        super().configure(width=final_width, height=self._req_height)

    def _on_resize(self, event: tk.Event) -> None:
        """Gerencia redimensionamento com debounce.

        Logic: Triggers redraw on resize."""
        self._draw(event.width, event.height, delay=60)

    def _on_enter(self, _event: tk.Event) -> None:
        """Mouse entrou no botão.

        Logic: Sets hover state and redraws."""
        self._is_hovering = True
        self._draw()

    def _on_leave(self, _event: tk.Event) -> None:
        """Mouse saiu do botão.

        Logic: Unsets hover/pressed state and redraws."""
        self._is_hovering = False
        self._is_pressed = False
        self._draw()

    def _on_press(self, _event: tk.Event) -> None:
        """Botão do mouse pressionado.

        Logic: Sets pressed state and redraws."""
        self._is_pressed = True
        self._draw()

    def _on_release(self, event: tk.Event) -> None:
        """Botão do mouse solto.

        Logic: Unsets pressed state, checks if click is valid,
        triggers command if so."""
        self._is_pressed = False
        try:
            if self.winfo_containing(event.x_root, event.y_root) == self:
                self._is_hovering = True
                if self.command:
                    self.after(10, self._safe_command_exec)
            else:
                self._is_hovering = False
        except Exception:
            self._is_hovering = False
        if self.winfo_exists():
            self._draw()

    def _safe_command_exec(self) -> None:
        """Logic: Executes the command callback safely."""
        if self.command:
            try:
                self.command()
            except Exception as e:
                logger.error("Button command error: %s", e, exc_info=True)

    def on_theme_change(self, _note: Any = None) -> None:
        """Logic: Updates colors and redraws on theme change."""
        if not self.winfo_exists():
            Publisher.unsubscribe(str(id(self)))
            return
        self.color_manager.update_palette()
        self.color_manager.update_button_colors(self.variant)
        self.configure(bg=self.color_manager.palette["parent"])
        self._draw()

    def _draw(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        delay: int = 0,
    ) -> None:
        """Agenda ou executa a renderização.

        Logic: Schedules or runs _render."""
        if self._draw_job:
            self.after_cancel(self._draw_job)
            self._draw_job = None
        if delay > 0:
            self._draw_job = self.after(
                delay, lambda: self._render(width, height)
            )
        else:
            self._render(width, height)

    def _render(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> None:
        """Renderização real do botão.

        Logic: Determines colors based on state, draws background via
        renderer, and draws text."""
        w = width or self.winfo_width()
        h = height or self.winfo_height()
        if w <= 1 or h <= 1:
            return
        p = self.color_manager.button_palette
        parent_bg = self.color_manager.palette["parent"]
        if self._state == "disabled":
            fill = p["disabled_bg"] if self.variant == "filled" else parent_bg
            border = (
                p["disabled_fg"]
                if self.variant == "outlined"
                else p["disabled_bg"]
            )
            text_color = p["disabled_fg"]
        else:
            if self._is_pressed:
                fill = p["pressed"]
            elif self._is_hovering:
                fill = p["hover"]
            else:
                fill = p["fg"] if self.variant == "filled" else parent_bg
            border = p["fg"] if self.variant == "outlined" else fill
            text_color = p["text"]
        self._renderer.generate_slices(
            {
                "bg": fill,
                "bg_base": fill,
                "bg_hover": fill,
                "border": border,
                "shadow": "#000000",
                "parent": parent_bg,
            }
        )
        self._renderer.draw_on_canvas(self, w, h)
        self.delete("fg_text")
        x = (
            w / 2
            if self._anchor == "center"
            else self.padding[0]
            if self._anchor == "w"
            else w - self.padding[0]
        )
        self.create_text(
            x,
            h / 2,
            text=self.text,
            fill=text_color,
            font=self.font,
            anchor=self._anchor,
            tags="fg_text",
        )
        if self._is_pressed:
            self.move("all", 0, 1)
