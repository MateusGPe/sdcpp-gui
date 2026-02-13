from __future__ import annotations

import tkinter as tk
from typing import Any, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import NW, VERTICAL
from ttkbootstrap.publisher import Channel, Publisher


class SmoothScrollFrame(ttk.Frame):
    """
    Um container com rolagem suave customizada.
    Substitui o ScrolledFrame padrão para corrigir o 'pulo' de quadros.
    """

    def __init__(
        self, parent: tk.Widget, autohide: bool = False, **kwargs: Any
    ) -> None:
        """Logic: Initializes frame with canvas, scrollbar, and inner
        content frame."""
        self.bootstyle = kwargs.get("bootstyle", "")
        super().__init__(parent, **kwargs)
        self.autohide = autohide
        self._scrolling_enabled = True
        self._scrollbar_visible = True
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(
            self,
            orient=VERTICAL,
            command=self.canvas.yview,
            bootstyle=self.bootstyle,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        if not self.autohide:
            self.scrollbar.grid(row=0, column=1, sticky="ns")
        else:
            self._scrollbar_visible = False
        self.content = ttk.Frame(self.canvas, bootstyle=self.bootstyle)
        self.container = self.content
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.content, anchor=NW
        )
        self.content.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        Publisher.subscribe(
            name=str(id(self)), func=self._on_theme_change, channel=Channel.STD
        )
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._scrolling_enabled = True
        self.enable_scrolling()
        self._update_colors()

    def _on_theme_change(self, _event: Optional[Any] = None) -> None:
        """Logic: Updates colors on theme change."""
        if self.winfo_exists():
            self._update_colors()

    def _update_colors(self) -> None:
        """Atualiza a cor de fundo do canvas para combinar com o estilo.

        Logic: Sets canvas background color based on bootstyle/theme."""
        style = ttk.Style()
        bg_color = style.colors.bg
        if self.bootstyle:
            for part in self.bootstyle.split():
                if hasattr(style.colors, part):
                    bg_color = getattr(style.colors, part)
                    break
        self.canvas.configure(bg=bg_color)
        self.content.configure(bootstyle=self.bootstyle)
        self.scrollbar.configure(bootstyle=self.bootstyle)

    def _on_destroy(self, _event: tk.Event) -> None:
        """Logic: Unsubscribes events."""
        Publisher.unsubscribe(str(id(self)))

    def enable_scrolling(self) -> None:
        """Ativa a funcionalidade de rolagem e exibe a barra.

        Logic: Shows scrollbar and enables scroll bindings."""
        if not self._scrolling_enabled:
            self._scrolling_enabled = True
            if self.autohide:
                self._check_autohide()
            else:
                self.scrollbar.grid(row=0, column=1, sticky="ns")
                self._scrollbar_visible = True
        self.content.bind("<Enter>", self._bound_to_mousewheel)
        self.content.bind("<Leave>", self._unbound_to_mousewheel)
        self.canvas.bind("<Enter>", self._bound_to_mousewheel)
        self.canvas.bind("<Leave>", self._unbound_to_mousewheel)

    def disable_scrolling(self) -> None:
        """Desativa a funcionalidade de rolagem e oculta a barra.

        Logic: Hides scrollbar and removes scroll bindings."""
        if self._scrolling_enabled:
            self.scrollbar.grid_remove()
            self._scrollbar_visible = False
            self._scrolling_enabled = False
        self.content.unbind("<Enter>")
        self.content.unbind("<Leave>")
        self.canvas.unbind("<Enter>")
        self.canvas.unbind("<Leave>")
        self._unbound_to_mousewheel(None)

    def _on_frame_configure(self, _event: Optional[tk.Event] = None) -> None:
        """Atualiza a região de rolagem quando o conteúdo muda.

        Logic: Updates canvas scrollregion and checks autohide."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if self.autohide:
            self._check_autohide()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Garante que o frame interno tenha a largura do canvas.

        Logic: Resizes inner frame to match canvas width."""
        canvas_width = event.width
        self.canvas.itemconfig(self.window_id, width=canvas_width)
        if self.autohide:
            self._check_autohide()

    def _check_autohide(self) -> None:
        """Verifica se a barra de rolagem deve ser exibida ou oculta.

        Logic: Toggles scrollbar visibility based on content height vs
        canvas height."""
        if not self._scrolling_enabled:
            return
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        content_height = bbox[3]
        visible_height = self.canvas.winfo_height()
        if content_height > visible_height:
            if not self._scrollbar_visible:
                self.scrollbar.grid(row=0, column=1, sticky="ns")
                self._scrollbar_visible = True
        elif self._scrollbar_visible:
            self.scrollbar.grid_remove()
            self._scrollbar_visible = False
            self.canvas.yview_moveto(0)

    def _bound_to_mousewheel(self, _event: tk.Event) -> None:
        """Ativa o scroll quando o mouse entra na área.

        Logic: Binds global mousewheel events to this widget."""
        if not self._scrolling_enabled:
            return
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbound_to_mousewheel(self, _event: Optional[tk.Event]) -> None:
        """Desativa o scroll quando o mouse sai.

        Logic: Unbinds global mousewheel events."""
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event: tk.Event) -> str:
        """Lógica de rolagem suave.

        Logic: Performs vertical scrolling on canvas."""
        should_scroll = self._scrolling_enabled
        first, last = self.canvas.yview()
        if float(first) <= 0.0 and float(last) >= 1.0:
            should_scroll = False
        if self.autohide and (not self._scrollbar_visible):
            should_scroll = False
        if (
            hasattr(self, "winfo_exists")
            and self.winfo_exists()
            and should_scroll
        ):
            if event.delta:
                if abs(event.delta) >= 120:
                    self.canvas.yview_scroll(
                        int(-1 * (event.delta / 120)), "units"
                    )
                else:
                    self.canvas.yview_scroll(
                        -1 if event.delta > 0 else 1, "units"
                    )
            elif event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
        return "break"
