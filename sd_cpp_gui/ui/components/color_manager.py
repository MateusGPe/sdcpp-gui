from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, Optional, TypedDict, Union, cast

import ttkbootstrap as tb
from ttkbootstrap.constants import LIGHT
from ttkbootstrap.style import Colors

from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components.nine_slices import ColorPalette

logger = get_logger("ColorManager")


class ColorOverrides(TypedDict):
    """Define as intenções de cor fornecidas pelo usuário."""

    bg: Optional[str]
    border: Optional[str]
    hover: Optional[str]
    shadow: Optional[str]
    focus: Optional[str]


def blend_colors(color1: str, color2: str, weight: float) -> str:
    """
    Mistura duas cores hexadecimais.
    :param weight: 0.0 a 1.0 (quanto maior, mais de color1)

    Logic: Blends two hex colors."""
    if not color1 or not isinstance(color1, str):
        return color2 if color2 and isinstance(color2, str) else "#ffffff"
    if not color2 or not isinstance(color2, str):
        return color1
    try:
        c1 = Colors.hex_to_rgb(color1)
        c2 = Colors.hex_to_rgb(color2)
        r = c1[0] * weight + c2[0] * (1 - weight)
        g = c1[1] * weight + c2[1] * (1 - weight)
        b = c1[2] * weight + c2[2] * (1 - weight)
        return Colors.rgb_to_hex(r, g, b)
    except (ValueError, TypeError, AttributeError):
        logger.debug("Falha ao misturar cores: %s e %s", color1, color2)
        return color1


class ColorManager:
    """
    Responsabilidade: Gerenciar a paleta de cores.
    Resolve cores baseadas no tema, overrides do usuário,
      bootstyle e contexto do widget pai.
    """

    def __init__(
        self,
        master_widget: tk.Misc,
        overrides: Dict[str, Optional[str]],
        bootstyle: str = "",
    ) -> None:
        """Logic: Initializes manager with overrides and defaults."""
        self.master = master_widget
        self.overrides = overrides
        self.bootstyle = bootstyle
        self.is_focused = False
        self.is_hovering = False
        self.is_disabled = False
        self.original_border_override = overrides.get("border")
        self.palette: ColorPalette = {
            "bg": "#ffffff",
            "bg_base": "#ffffff",
            "bg_hover": "#ffffff",
            "border": "#000000",
            "shadow": "#000000",
            "parent": "#ffffff",
        }
        self._resolved_cache: Dict[str, str] = {}
        self.is_light_theme: Optional[bool] = None

    def update_palette(self) -> ColorPalette:
        """Recalcula e retorna o TypedDict de cores atualizado.

        Logic: Resolves final colors for bg, border, shadow, etc.
        based on state and theme.
        """
        logger.debug(
            "Updating palette for widget. Bootstyle: '%s', Overrides: %s",
            self.bootstyle,
            self.overrides,
        )
        self._resolved_cache.clear()
        try:
            style = tb.Style.get_instance()
        except Exception:
            logger.warning("Não foi possível obter instância do tb.Style.")
            style = None
        t_border = "#ced4da"
        t_bg = "#ffffff"
        t_focus = "#2081d5"
        t_boot_color = None
        if style:
            try:
                colors: Colors = cast(Colors, style.colors)
                self.is_light_theme = style.theme.type == LIGHT
                if (
                    hasattr(style, "theme")
                    and style.theme
                    and self.is_light_theme
                ):
                    t_border = getattr(colors, "border", t_border)
                elif hasattr(style, "colors"):
                    t_border = getattr(colors, "selectbg", t_border)
                if hasattr(style, "colors"):
                    t_bg = getattr(colors, "inputbg", t_bg)
                    t_focus = getattr(colors, "primary", t_focus)
                if self.bootstyle:
                    for color_name in [
                        "primary",
                        "secondary",
                        "success",
                        "info",
                        "warning",
                        "danger",
                        "light",
                        "dark",
                    ]:
                        if color_name in self.bootstyle:
                            t_boot_color = getattr(
                                style.colors, color_name, None
                            )
                            break
            except Exception as e:
                logger.error("Erro ao resolver cores do tema: %s", e)
        target_border_default = t_border
        target_focus_default = t_boot_color if t_boot_color else t_focus
        try:
            self.palette["parent"] = self._detect_parent_bg(self.master)
            current_override = self.overrides.get("border")
            if (
                current_override
                and current_override != self.original_border_override
            ):
                self.palette["border"] = self._resolve_color(current_override)
            elif self.is_focused:
                raw_focus = self.overrides.get("focus") or target_focus_default
                self.palette["border"] = self._resolve_color(raw_focus)
            else:
                raw_border = (
                    self.original_border_override or target_border_default
                )
                self.palette["border"] = self._resolve_color(raw_border)
            target_shadow_default = t_boot_color if t_boot_color else "#000000"
            raw_shadow = self.overrides.get("shadow") or target_shadow_default
            self.palette["shadow"] = self._resolve_color(raw_shadow)
            raw_bg = self.overrides.get("bg") or t_bg
            self.palette["bg_base"] = self._resolve_color(raw_bg)
            if self.overrides.get("hover"):
                self.palette["bg_hover"] = self._resolve_color(
                    self.overrides["hover"]
                )
            else:
                self.palette["bg_hover"] = self.palette["bg_base"]
            if self.is_hovering:
                self.palette["bg"] = self.palette["bg_hover"]
            else:
                self.palette["bg"] = self.palette["bg_base"]
            if self.is_disabled:
                self.palette["bg"] = blend_colors(
                    self.palette["border"], self.palette["parent"], 0.1
                )
                self.palette["border"] = blend_colors(
                    self.palette["border"], self.palette["parent"], 0.2
                )
                self.palette["bg_hover"] = self.palette["bg"]
        except Exception as e:
            logger.error(
                "Erro crítico ao atualizar paleta: %s", e, exc_info=True
            )
        logger.debug("Palette updated: %s", self.palette)
        return self.palette

    def set_hover_state(self, is_hovering: bool) -> None:
        """Define o estado de hover.

        Logic: Updates the hover state flag."""
        self.is_hovering = is_hovering

    def set_disabled_state(self, is_disabled: bool) -> None:
        """Define se o widget está desabilitado.

        Logic: Updates the disabled state flag."""
        self.is_disabled = is_disabled

    def set_focus_state(self, is_focused: bool) -> None:
        """Define se o widget tem foco de teclado.

        Logic: Updates the focus state flag."""
        self.is_focused = is_focused

    def set_temporary_border(self, color: Optional[str]) -> None:
        """Define uma cor de borda temporária (ex: erro).

        Logic: Sets a temporary border color override."""
        if color:
            self.overrides["border"] = color
        else:
            self.overrides["border"] = self.original_border_override

    def _resolve_color(self, color: Union[str, Any]) -> str:
        """Resolve nomes de cores, hex ou referências do tema.

        Logic: Converts color names/bootstyle keys to hex codes."""
        if not color:
            return "#ffffff"
        color_key = str(color)
        if color_key in self._resolved_cache:
            return self._resolved_cache[color_key]
        resolved = "#ffffff"
        try:
            try:
                style = tb.Style.get_instance() or tb.Style()
            except Exception:
                style = None
            if style and hasattr(style.colors, color_key):
                resolved = getattr(style.colors, color_key)
            else:
                master = self.master
                if (
                    master
                    and hasattr(master, "winfo_exists")
                    and master.winfo_exists()
                    and hasattr(master, "winfo_rgb")
                ):
                    rgb = master.winfo_rgb(color_key)
                    resolved = (
                        f"#{int(rgb[0] / 256):02x}"
                        f"{int(rgb[1] / 256):02x}"
                        f"{int(rgb[2] / 256):02x}"
                    )
                elif color_key.startswith("#"):
                    resolved = color_key
        except Exception as e:
            if color_key.startswith("#"):
                logger.debug(
                    "Usando fallback direto para hex: %s. Erro: %s",
                    color_key,
                    e,
                )
                resolved = color_key
        self._resolved_cache[color_key] = resolved
        logger.debug("Resolved color '%s' -> '%s'", color_key, resolved)
        return resolved

    def _detect_parent_bg(self, widget: tk.Misc) -> str:
        """Logic: Traverses widget hierarchy to find parent background color."""
        if not widget:
            return "#ffffff"
        try:
            if hasattr(widget, "winfo_exists") and (not widget.winfo_exists()):
                return "#ffffff"
        except (tk.TclError, Exception):
            return "#ffffff"
        bg = None
        curr: Optional[tk.Misc] = widget
        for _ in range(4):
            if not curr:
                break
            try:
                if hasattr(curr, "cget"):
                    bg = curr.cget("bg")
                    if (
                        bg
                        and str(bg) != ""
                        and (not str(bg).startswith("System"))
                    ):
                        return self._resolve_color(bg)
            except (tk.TclError, AttributeError):
                pass
            try:
                style = tb.Style.get_instance() or tb.Style()
                w_style = None
                if hasattr(curr, "cget"):
                    try:
                        w_style = curr.cget("style")
                    except tk.TclError:
                        pass
                if not w_style and hasattr(curr, "winfo_class"):
                    w_style = curr.winfo_class()
                if w_style:
                    lookup = style.lookup(w_style, "background")
                    if lookup and str(lookup) != "":
                        return self._resolve_color(lookup)
            except Exception:
                pass
            if hasattr(curr, "master"):
                curr = curr.master
            else:
                break
        try:
            style = tb.Style.get_instance() or tb.Style()
            bg = getattr(style.colors, "bg", "#ffffff")
        except Exception as e:
            logger.debug("Falha na detecção de background do pai: %s", e)
            bg = "#ffffff"
        return self._resolve_color(bg)

    def has_hover(self) -> bool:
        """Logic: Checks if a hover color override exists."""
        return self.overrides.get("hover", None) is not None

    def _get_relative_luminance(self, r: int, g: int, b: int) -> float:
        """
        Calcula a luminância relativa (WCAG 2.0).
        """

        def linearize(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        R = linearize(r)
        G = linearize(g)
        B = linearize(b)
        return 0.2126 * R + 0.7152 * G + 0.0722 * B

    def _get_contrast_ratio(self, lum1: float, lum2: float) -> float:
        """
        Calcula a razão de contraste (1:1 a 21:1).
        """
        l1 = max(lum1, lum2)
        l2 = min(lum1, lum2)
        return (l1 + 0.05) / (l2 + 0.05)

    def _mix_colors(self, hex1: str, hex2: str, weight: float) -> str:
        """
        Mistura duas cores (Interpolation).
        weight 0.0 = hex1 pura, weight 1.0 = hex2 pura.


        Logic: Mixes two hex colors."""
        r1, g1, b1 = Colors.hex_to_rgb(hex1)
        r2, g2, b2 = Colors.hex_to_rgb(hex2)
        r = r1 + (r2 - r1) * weight
        g = g1 + (g2 - g1) * weight
        b = b1 + (b2 - b1) * weight
        ratio = max(r, g, b)
        dec = ratio - min(r, g, b)
        if ratio != 0:
            r = max(min((r - dec) / ratio, 1), 0)
            g = max(min((g - dec) / ratio, 1), 0)
            b = max(min((b - dec) / ratio, 1), 0)
        return Colors.rgb_to_hex(r, g, b)

    def ensure_contrast(
        self, bg_hex: str, fg_hex: str, min_ratio: float = 3.5
    ) -> str:
        """
        Ajusta a cor de frente (fg) para garantir contraste contra o fundo (bg).
        Usa interpolação com Branco/Preto para evitar cores 'lavadas'.

        Logic: Adjusts foreground color to meet contrast ratio against
        background."""
        if not bg_hex or not fg_hex:
            return fg_hex
        try:
            r_bg, g_bg, b_bg = Colors.hex_to_rgb(bg_hex)
            r_fg, g_fg, b_fg = Colors.hex_to_rgb(fg_hex)
            lum_bg = self._get_relative_luminance(r_bg, g_bg, b_bg)
            lum_fg = self._get_relative_luminance(r_fg, g_fg, b_fg)
            ratio = self._get_contrast_ratio(lum_bg, lum_fg)
            if ratio >= min_ratio:
                return fg_hex
            target_is_white = lum_bg < 0.5
            target_hex = "#ffffff" if target_is_white else "#000000"
            best_hex = fg_hex
            best_ratio = ratio
            for i in range(1, 20):
                weight = i * 0.05
                new_hex = self._mix_colors(fg_hex, target_hex, weight)
                nr, ng, nb = Colors.hex_to_rgb(new_hex)
                nlum = self._get_relative_luminance(nr, ng, nb)
                nratio = self._get_contrast_ratio(lum_bg, nlum)
                if nratio > best_ratio:
                    best_ratio = nratio
                    best_hex = new_hex
                if nratio >= min_ratio:
                    return new_hex
            if best_ratio < 1:
                return target_hex
            return best_hex
        except Exception as e:
            logger.error("Erro no ensure_contrast: %s", e, exc_info=True)
            return fg_hex
